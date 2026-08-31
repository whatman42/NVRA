"""Safe paper recovery for N.U.N.G. Phase 5C — no live state reconstruction."""

from __future__ import annotations

from typing import Any, Optional

from god.execution_contract.models import ExecutionIntent

from .engine import PaperExecutionEngine
from .models import PaperExecution
from .reconciliation import ReconciliationRecord, ReconciliationStatus, PaperReconciler
from .state import PaperState


class PaperRecoveryService:
    """
    CONSISTENT → reusable
    DUPLICATE → reuse canonical
    CORRUPTED / STALE → rebuild via re-simulation when possible
    MISSING_INTENT / MISMATCHED → reject
    """

    def __init__(
        self,
        state: Optional[PaperState] = None,
        engine: Optional[PaperExecutionEngine] = None,
        reconciler: Optional[PaperReconciler] = None,
        max_recovery_attempts: int = 3,
    ) -> None:
        self.state = state or PaperState()
        self.engine = engine or PaperExecutionEngine(state=self.state)
        self.reconciler = reconciler or PaperReconciler()
        self.max_recovery_attempts = max_recovery_attempts

    def recover(
        self,
        execution: PaperExecution,
        intent: Optional[ExecutionIntent],
        *,
        market_observation: Optional[dict[str, Any]] = None,
        snapshot_id: Optional[str] = None,
        now_iso: Optional[str] = None,
    ) -> tuple[ReconciliationRecord, Optional[PaperExecution]]:
        rec = self.reconciler.reconcile(execution, intent, now_iso=now_iso)

        if rec.status in (
            ReconciliationStatus.CONSISTENT,
            ReconciliationStatus.DUPLICATE,
        ):
            canonical = self.state.get(execution.paper_execution_id) or execution
            return rec, canonical

        if rec.status in (
            ReconciliationStatus.MISSING_INTENT,
            ReconciliationStatus.MISMATCHED_INTENT,
            ReconciliationStatus.INVALID,
            ReconciliationStatus.UNKNOWN,
        ):
            return rec, None

        if rec.status in (ReconciliationStatus.CORRUPTED, ReconciliationStatus.STALE):
            if intent is None:
                return rec, None
            # rebuild from canonical intent + observation — never guess
            rebuilt = self.engine.simulate(
                intent,
                market_observation=market_observation,
                snapshot_id=snapshot_id,
                now_iso=now_iso,
            )
            return rec, rebuilt

        return rec, None
