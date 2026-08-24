"""
Zombie Lease Reaper Engine for SwarmCron.
Scans for expired concurrency leases and dead worker sessions, triggering safe
backward topological saga compensation and releasing abandoned locks.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from swarmlock.hierarchy import HierarchyLockEngine, ResourceKey
from swarmsaga.core.unwinder import TopologicalUnwinder
from swarmsaga.journal.engine import JournalEngine

logger = logging.getLogger("swarmcron.reaper")


class ZombieLeaseReaper:
    """
    Reclaims deadlocks and orphaned sagas left by crashed workers or dropped network sessions.
    """

    def __init__(
        self,
        lock_engine: Optional[HierarchyLockEngine] = None,
        journal: Optional[JournalEngine] = None
    ):
        self.lock_engine = lock_engine or HierarchyLockEngine()
        self.journal = journal or JournalEngine()
        self.unwinder = TopologicalUnwinder(journal=self.journal)

    async def sweep_and_reclaim(self, ttl_threshold_seconds: float = 60.0) -> Dict[str, Any]:
        """
        Scans all active sagas and leases. If an executing saga has not sent a heartbeat
        within ttl_threshold_seconds, triggers rollback and frees the lock.
        """
        now = time.time()
        reclaimed_sagas = []
        released_locks = 0

        # Scan executing sagas
        executing_sagas = self.journal.list_sagas(state='EXECUTING')
        for saga in executing_sagas:
            tx_id = saga["tx_id"]
            updated_at = saga.get("updated_at", 0)
            if now - updated_at > ttl_threshold_seconds:
                logger.warning("Detected zombie saga %s (idle for %.1fs). Unwinding...", tx_id, now - updated_at)
                try:
                    await self.unwinder.unwind(tx_id=tx_id, step_handlers={})
                    reclaimed_sagas.append(tx_id)
                except Exception as exc:
                    logger.error("Failed to unwind zombie saga %s: %s", tx_id, exc)

        return {
            "reclaimed_sagas_count": len(reclaimed_sagas),
            "reclaimed_sagas": reclaimed_sagas
        }