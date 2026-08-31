"""NullExecutionProvider — N.U.N.G. Phase 5A. Never contacts a broker."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import (
    ExecutionIntent,
    ExecutionResult,
    IntentStatus,
    ResultStatus,
    build_exec_provenance,
    make_result_id,
)


class NullExecutionProvider:
    """
    Simulated / null execution only.
    executed=False, simulated=True always.
    """

    provider_id = "null"

    def __init__(self) -> None:
        self._cache: dict[str, ExecutionResult] = {}

    def execute(self, intent: ExecutionIntent) -> ExecutionResult:
        if intent.intent_id in self._cache:
            return self._cache[intent.intent_id]

        if intent.intent_status != IntentStatus.VALID:
            payload = {
                "intent_id": intent.intent_id,
                "status": "REJECTED",
                "provider": self.provider_id,
            }
            rid = make_result_id(payload)
            result = ExecutionResult(
                result_id=rid,
                intent_id=intent.intent_id,
                decision_id=intent.decision_id,
                cycle_id=intent.cycle_id,
                status=ResultStatus.REJECTED,
                provider=self.provider_id,
                executed=False,
                simulated=True,
                created_at=utc_now(),
                content_hash=content_hash(payload),
                reason_codes=("intent_not_valid",),
                provenance=build_exec_provenance(payload),
                notes="rejected_non_valid_intent",
            )
            self._cache[intent.intent_id] = result
            return result

        payload = {
            "intent_id": intent.intent_id,
            "decision_id": intent.decision_id,
            "cycle_id": intent.cycle_id,
            "status": ResultStatus.NULL_EXECUTED.value,
            "provider": self.provider_id,
            "executed": False,
            "simulated": True,
        }
        rid = make_result_id(payload)
        result = ExecutionResult(
            result_id=rid,
            intent_id=intent.intent_id,
            decision_id=intent.decision_id,
            cycle_id=intent.cycle_id,
            status=ResultStatus.NULL_EXECUTED,
            provider=self.provider_id,
            executed=False,
            simulated=True,
            created_at=utc_now(),
            content_hash=content_hash(payload),
            reason_codes=("null_provider", "no_real_execution"),
            provenance=build_exec_provenance(payload),
            notes="SIMULATED_NULL_EXECUTION — no broker, no order, no position",
        )
        self._cache[intent.intent_id] = result
        return result
