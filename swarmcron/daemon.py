"""
Background Hypervisor Reaper & Invariant Monitor Daemon for SwarmCron.
Coordinating lease reclamation, worktree garbage collection, and Merkle ledger audits.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from swarmcron.auditor import ScheduledLedgerAuditor
from swarmcron.gc import WorktreeGarbageCollector
from swarmcron.reaper import ZombieLeaseReaper
from swarmledger.storage.engine import StorageEngine
from swarmsaga.journal.engine import JournalEngine

logger = logging.getLogger("swarmcron.daemon")


class SwarmcronDaemon:
    """
    Periodic background guardian for the Swarm Hypervisor substrate.
    """

    def __init__(
        self,
        journal_db_path: Optional[str | Path] = None,
        ledger_db_path: Optional[str | Path] = None,
        base_sagas_dir: Optional[str | Path] = None,
        reaper_interval_seconds: float = 30.0,
        gc_interval_seconds: float = 300.0,
        audit_interval_seconds: float = 600.0
    ):
        self.journal = JournalEngine(db_path=journal_db_path)
        self.ledger = StorageEngine(db_path=ledger_db_path)
        self.reaper = ZombieLeaseReaper(journal=self.journal)
        self.gc = WorktreeGarbageCollector(base_sagas_dir=base_sagas_dir)
        self.auditor = ScheduledLedgerAuditor(engine=self.ledger)

        self.reaper_interval = reaper_interval_seconds
        self.gc_interval = gc_interval_seconds
        self.audit_interval = audit_interval_seconds
        self._running = False

    async def run_once(self) -> dict:
        """Executes a single maintenance cycle across reaper, GC, and auditor."""
        reap_res = await self.reaper.sweep_and_reclaim()
        cleaned_worktrees = self.gc.sweep_stale_worktrees()
        audit_res = self.auditor.audit_all_spans()

        return {
            "reaped_sagas": reap_res["reclaimed_sagas_count"],
            "cleaned_worktrees": len(cleaned_worktrees),
            "audit_passed_spans": audit_res.passed_spans,
            "audit_failed_spans": audit_res.failed_spans
        }

    async def start(self):
        self._running = True
        logger.info("Starting Swarmcron Background Daemon...")
        while self._running:
            try:
                summary = await self.run_once()
                logger.debug("Swarmcron cycle complete: %s", summary)
            except Exception as exc:
                logger.error("Error in Swarmcron cycle: %s", exc)
            await asyncio.sleep(self.reaper_interval)

    def stop(self):
        self._running = False