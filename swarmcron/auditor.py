"""
Periodic Merkle DAG Auditor for SwarmCron.
Executes automated cryptographic integrity verifications over SwarmLedger databases.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from swarmledger.storage.auditor import AuditReport, CryptographicAuditor
from swarmledger.storage.engine import StorageEngine

logger = logging.getLogger("swarmcron.auditor")


@dataclass
class SwarmAuditSummary:
    spans_audited: int
    passed_spans: int
    failed_spans: int
    total_violations: int
    reports: Dict[str, AuditReport]


class ScheduledLedgerAuditor:
    """
    Automates scheduled background integrity audits across the Merkle provenance DAG.
    """

    def __init__(self, engine: StorageEngine):
        self.engine = engine
        self.auditor = CryptographicAuditor(engine)

    def audit_all_spans(self) -> SwarmAuditSummary:
        spans = self.engine.list_spans()
        reports: Dict[str, AuditReport] = {}
        passed = 0
        failed = 0
        total_violations = 0

        for span in spans:
            span_id = span['span_id'] if isinstance(span, dict) else span
            report = self.auditor.verify_span(span_id)
            reports[span_id] = report
            if report.passed:
                passed += 1
            else:
                failed += 1
                total_violations += len(report.violations)
                logger.error("Audit failure in span %s: %s", span_id, report.violations)

        return SwarmAuditSummary(
            spans_audited=len(spans),
            passed_spans=passed,
            failed_spans=failed,
            total_violations=total_violations,
            reports=reports
        )