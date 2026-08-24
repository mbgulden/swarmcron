"""
Tests for SwarmCron Zombie Lease Reaper, Worktree GC, and Merkle Auditor.
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path
import pytest

from swarmcron.auditor import ScheduledLedgerAuditor
from swarmcron.daemon import SwarmcronDaemon
from swarmcron.gc import WorktreeGarbageCollector
from swarmcron.reaper import ZombieLeaseReaper
from swarmledger.core.node import EventType
from swarmledger.storage.engine import StorageEngine
from swarmsaga.journal.engine import JournalEngine


def test_zombie_lease_reaper_unwinds_orphaned_saga():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            j_db = Path(tmpdir) / "journal.db"
            journal = JournalEngine(db_path=j_db)

            tx_id = "tx_zombie_1"
            journal.begin_saga(tx_id, "crashed_worker")

            # Artificially age the saga timestamp to 100 seconds ago
            with journal._lock:
                conn = journal._get_conn()
                conn.execute("UPDATE sagas SET updated_at = ? WHERE tx_id = ?", (time.time() - 100.0, tx_id))
                conn.commit()
                conn.close()

            reaper = ZombieLeaseReaper(journal=journal)
            result = await reaper.sweep_and_reclaim(ttl_threshold_seconds=30.0)

            assert result["reclaimed_sagas_count"] == 1
            assert result["reclaimed_sagas"] == [tx_id]

            # Saga state must now be ABORTED
            saga_record = journal.get_saga(tx_id)
            assert saga_record["state"] == "ABORTED"

    asyncio.run(_run())


def test_worktree_gc_prunes_stale_directories():
    with tempfile.TemporaryDirectory() as tmpdir:
        sagas_dir = Path(tmpdir) / ".sagas"
        sagas_dir.mkdir()

        stale_tree = sagas_dir / "tx_stale_123"
        stale_tree.mkdir()
        (stale_tree / "file.py").write_text("print('stale')")

        fresh_tree = sagas_dir / "tx_fresh_456"
        fresh_tree.mkdir()
        (fresh_tree / "file.py").write_text("print('fresh')")

        # Set modification time of stale tree to 2 hours ago
        past_time = time.time() - 7200.0
        os.utime(stale_tree, (past_time, past_time))

        gc = WorktreeGarbageCollector(base_sagas_dir=sagas_dir)
        cleaned = gc.sweep_stale_worktrees(max_age_seconds=3600.0)

        assert cleaned == ["tx_stale_123"]
        assert not stale_tree.exists()
        assert fresh_tree.exists()


def test_scheduled_ledger_auditor_reports_integrity():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "ledger.db"
        engine = StorageEngine(db_path=db_path)

        span_id = "span_audit_cron_1"
        n1 = engine.append_node(span_id, EventType.PROMPT, "user", {"query": "hello"})
        n2 = engine.append_node(span_id, EventType.COMMIT, "agent", {"res": "ok"}, [n1.node_id])

        auditor = ScheduledLedgerAuditor(engine)
        summary = auditor.audit_all_spans()

        assert summary.spans_audited == 1
        assert summary.passed_spans == 1
        assert summary.failed_spans == 0
        assert summary.total_violations == 0


def test_swarmcron_daemon_run_once():
    async def _run():
        with tempfile.TemporaryDirectory() as tmpdir:
            j_db = Path(tmpdir) / "journal.db"
            l_db = Path(tmpdir) / "ledger.db"
            sagas_dir = Path(tmpdir) / ".sagas"
            sagas_dir.mkdir()

            daemon = SwarmcronDaemon(
                journal_db_path=j_db,
                ledger_db_path=l_db,
                base_sagas_dir=sagas_dir
            )

            res = await daemon.run_once()
            assert "reaped_sagas" in res
            assert "cleaned_worktrees" in res
            assert "audit_passed_spans" in res

    asyncio.run(_run())