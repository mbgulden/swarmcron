"""
Worktree & Artifact Garbage Collector for SwarmCron.
Prunes stale .sagas/<tx_id> directories and temporary scratch workspaces.
"""

from __future__ import annotations

import logging
import shutil
import time
from pathlib import Path

logger = logging.getLogger("swarmcron.gc")


class WorktreeGarbageCollector:
    """
    Automates disk space reclamation for abandoned saga worktrees.
    """

    def __init__(self, base_sagas_dir: Path | str | None = None):
        self.base_dir = Path(base_sagas_dir or (Path.cwd() / ".sagas"))

    def sweep_stale_worktrees(self, max_age_seconds: float = 3600.0) -> list[str]:
        """
        Removes any worktree directory whose last modification time exceeds max_age_seconds.
        """
        if not self.base_dir.exists():
            return []

        cleaned: list[str] = []
        now = time.time()

        for item in self.base_dir.iterdir():
            if item.is_dir():
                try:
                    mtime = item.stat().st_mtime
                    age = now - mtime
                    if age > max_age_seconds:
                        logger.info("Pruning stale worktree %s (age: %.1f hours)", item.name, age / 3600.0)
                        shutil.rmtree(item, ignore_errors=True)
                        cleaned.append(item.name)
                except Exception as exc:  # noqa: BLE001 - keep pruning other worktrees when one fails
                    logger.error("Failed to prune worktree %s: %s", item.name, exc)

        return cleaned