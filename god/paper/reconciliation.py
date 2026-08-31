"""Phase 5C — N.U.N.G. paper execution reconciliation. Paper-only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.execution_contract.models import ExecutionIntent
from god.research.provenance import content_hash

from .models import PaperExecution, PaperStatus, SCHEMA_VERSION, build_paper_provenance


class ReconciliationStatus(str, Enum):
    CONSISTENT = "CONSISTENT"
    DUPLICATE = "DUPLICATE"
    MISSING_INTENT = "MISSING_INTENT"
    MISMATCHED_INTENT = "MISMATCHED_INTENT"
    CORRUPTED = "CORRUPTED"
    STALE = "STALE"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ReconciliationRecord:
    record_id: str
    paper_execution_id: str
    intent_id: str
    status: ReconciliationStatus
    content_hash: str
    reasons: tuple[str, ...] = ()
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "paper_execution_id": self.paper_execution_id,
            "intent_id": self.intent_id,
            "status": self.status.value,
            "content_hash": self.content_hash,
            "reasons": list(self.reasons),
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


def _recalc_paper_hash(execution: PaperExecution) -> str:
    payload = {
        "paper_execution_id": execution.paper_execution_id,
        "intent_id": execution.intent_id,
        "decision_id": execution.decision_id,
        "status": execution.status.value,
        "fill_id": execution.fill.fill_id if execution.fill else "",
    }
    return content_hash(payload)


def reconcile(
    execution: PaperExecution,
    intent: Optional[ExecutionIntent],
    *,
    expected_schema: str = SCHEMA_VERSION,
    now_iso: Optional[str] = None,
) -> ReconciliationRecord:
    """
    Compare PaperExecution to originating ExecutionIntent.
    Fail-closed: never silently repair.
    """
    reasons: list[str] = []

    if intent is None:
        status = ReconciliationStatus.MISSING_INTENT
        reasons.append("missing_intent")
    else:
        if execution.intent_id != intent.intent_id:
            status = ReconciliationStatus.MISMATCHED_INTENT
            reasons.append("intent_id_mismatch")
        elif execution.decision_id != intent.decision_id:
            status = ReconciliationStatus.MISMATCHED_INTENT
            reasons.append("decision_id_mismatch")
        elif execution.cycle_id != intent.cycle_id:
            status = ReconciliationStatus.MISMATCHED_INTENT
            reasons.append("cycle_id_mismatch")
        elif execution.symbol != intent.symbol:
            status = ReconciliationStatus.MISMATCHED_INTENT
            reasons.append("symbol_mismatch")
        elif execution.action != intent.intent_action.value:
            status = ReconciliationStatus.MISMATCHED_INTENT
            reasons.append("action_mismatch")
        else:
            status = ReconciliationStatus.CONSISTENT

    # schema / version
    if execution.schema_version != expected_schema:
        if status == ReconciliationStatus.CONSISTENT:
            status = ReconciliationStatus.STALE
        reasons.append("schema_mismatch")

    # hash integrity
    expected_hash = _recalc_paper_hash(execution)
    if execution.content_hash != expected_hash:
        status = ReconciliationStatus.CORRUPTED
        reasons.append("hash_mismatch")

    if not execution.provenance:
        if status == ReconciliationStatus.CONSISTENT:
            status = ReconciliationStatus.INVALID
        reasons.append("missing_provenance")

    # temporal
    if now_iso and execution.simulated_at and execution.simulated_at > now_iso:
        status = ReconciliationStatus.INVALID
        reasons.append("future_simulated_at")

    if execution.status not in (
        PaperStatus.PAPER_SIMULATED,
        PaperStatus.PAPER_REJECTED,
        PaperStatus.RECEIVED,
        PaperStatus.VALIDATED,
        PaperStatus.PAPER_FAILED,
    ):
        if status == ReconciliationStatus.CONSISTENT:
            status = ReconciliationStatus.UNKNOWN
        reasons.append(f"unexpected_status={execution.status.value}")

    payload = {
        "paper_execution_id": execution.paper_execution_id,
        "intent_id": execution.intent_id,
        "status": status.value,
        "reasons": reasons,
    }
    rid = "rec-" + content_hash(payload)[:24]
    return ReconciliationRecord(
        record_id=rid,
        paper_execution_id=execution.paper_execution_id,
        intent_id=execution.intent_id,
        status=status,
        content_hash=content_hash(payload),
        reasons=tuple(reasons),
        provenance=build_paper_provenance(payload),
        notes="paper_reconciliation_only",
    )


class PaperReconciler:
    def __init__(self, max_records: int = 500) -> None:
        self.max_records = max_records
        self._cache: dict[str, ReconciliationRecord] = {}
        self._order: list[str] = []

    def reconcile(
        self,
        execution: PaperExecution,
        intent: Optional[ExecutionIntent],
        *,
        now_iso: Optional[str] = None,
    ) -> ReconciliationRecord:
        rec = reconcile(execution, intent, now_iso=now_iso)
        if rec.record_id in self._cache:
            return self._cache[rec.record_id]
        self._cache[rec.record_id] = rec
        self._order.append(rec.record_id)
        while len(self._order) > self.max_records:
            old = self._order.pop(0)
            self._cache.pop(old, None)
        return rec
