"""Paper state consistency checks for N.U.N.G. Phase 5C."""

from __future__ import annotations

from typing import Optional

from god.research.provenance import content_hash

from .models import PaperExecution
from .reconciliation import ReconciliationStatus, reconcile
from .state import PaperState
from god.execution_contract.models import ExecutionIntent


def detect_duplicate(state: PaperState, execution: PaperExecution) -> bool:
    existing = state.get(execution.paper_execution_id)
    return existing is not None


def detect_conflict(state: PaperState, execution: PaperExecution) -> bool:
    """Same id but different content hash → conflict/corruption."""
    existing = state.get(execution.paper_execution_id)
    if existing is None:
        return False
    return existing.content_hash != execution.content_hash


def verify_hash(execution: PaperExecution) -> bool:
    payload = {
        "paper_execution_id": execution.paper_execution_id,
        "intent_id": execution.intent_id,
        "decision_id": execution.decision_id,
        "status": execution.status.value,
        "fill_id": execution.fill.fill_id if execution.fill else "",
    }
    return execution.content_hash == content_hash(payload)


def consistency_check(
    state: PaperState,
    execution: PaperExecution,
    intent: Optional[ExecutionIntent],
    *,
    now_iso: Optional[str] = None,
) -> ReconciliationStatus:
    if detect_conflict(state, execution):
        return ReconciliationStatus.CORRUPTED
    if not verify_hash(execution):
        return ReconciliationStatus.CORRUPTED
    rec = reconcile(execution, intent, now_iso=now_iso)
    if detect_duplicate(state, execution) and rec.status == ReconciliationStatus.CONSISTENT:
        return ReconciliationStatus.DUPLICATE
    return rec.status
