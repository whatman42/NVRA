"""ExecutionContractEngine — N.U.N.G. Phase 5A. ShadowDecision → null result."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import (
    ExecutionIntent,
    ExecutionResult,
    IntentAction,
    IntentStatus,
    ResultStatus,
    SCHEMA_VERSION,
    build_exec_provenance,
    make_intent_id,
    make_result_id,
)
from .null_provider import NullExecutionProvider
from .validator import ExecutionValidator


class ExecutionContractEngine:
    """
    Canonical path:
      ShadowDecision → ExecutionIntent → validate → NullExecutionProvider → ExecutionResult

    This is SIMULATED / NULL only. Not live trading.
    """

    def __init__(
        self,
        *,
        validator: Optional[ExecutionValidator] = None,
        provider: Optional[NullExecutionProvider] = None,
    ) -> None:
        self.validator = validator or ExecutionValidator()
        self.provider = provider or NullExecutionProvider()
        self._intent_cache: dict[str, ExecutionIntent] = {}
        self._result_cache: dict[str, ExecutionResult] = {}

    def execute_shadow(
        self,
        decision: Any,
        *,
        now_iso: Optional[str] = None,
        action: IntentAction = IntentAction.PAPER_ENTER,
    ) -> ExecutionResult:
        """
        Accepts a ShadowDecision-like object (or duck-typed attributes).
        Returns ExecutionResult with executed=False, simulated=True on success path.
        """
        intent = self.create_intent(decision, action=action, now_iso=now_iso)
        ok, status, reason = self.validator.validate(intent, now_iso=now_iso)
        if not ok:
            # rebuild intent with rejected status for provider path consistency
            rejected = ExecutionIntent(
                intent_id=intent.intent_id,
                decision_id=intent.decision_id,
                cycle_id=intent.cycle_id,
                opportunity_id=intent.opportunity_id,
                symbol=intent.symbol,
                strategy_ref=intent.strategy_ref,
                decision_status=intent.decision_status,
                intent_action=intent.intent_action,
                intent_status=status,
                created_at=intent.created_at,
                content_hash=intent.content_hash,
                valid_until=intent.valid_until,
                evidence_refs=intent.evidence_refs,
                provenance=intent.provenance,
                notes=reason,
            )
            if intent.intent_id in self._result_cache:
                return self._result_cache[intent.intent_id]
            result = self.provider.execute(rejected)
            self._result_cache[intent.intent_id] = result
            return result

        if intent.intent_id in self._result_cache:
            return self._result_cache[intent.intent_id]

        result = self.provider.execute(intent)
        self._result_cache[intent.intent_id] = result
        return result

    def create_intent(
        self,
        decision: Any,
        *,
        action: IntentAction = IntentAction.PAPER_ENTER,
        now_iso: Optional[str] = None,
    ) -> ExecutionIntent:
        decision_id = str(getattr(decision, "decision_id", "") or "")
        cycle_id = str(getattr(decision, "cycle_id", "") or "")
        opportunity_id = str(getattr(decision, "opportunity_id", "") or decision_id)
        symbol = str(getattr(decision, "symbol", "") or "")
        strategy_ref = getattr(decision, "strategy_ref", None)
        if strategy_ref is not None:
            strategy_ref = str(strategy_ref)
        status_obj = getattr(decision, "status", None)
        decision_status = (
            status_obj.value if hasattr(status_obj, "value") else str(status_obj or "")
        )
        evidence = getattr(decision, "evidence_refs", None) or []
        evidence_refs = tuple(str(x) for x in list(evidence)[:50])

        core = {
            "decision_id": decision_id,
            "cycle_id": cycle_id,
            "opportunity_id": opportunity_id,
            "symbol": symbol,
            "strategy_ref": strategy_ref,
            "decision_status": decision_status,
            "intent_action": action.value,
            "schema_version": SCHEMA_VERSION,
        }
        iid = make_intent_id(core)
        if iid in self._intent_cache:
            return self._intent_cache[iid]

        ch = content_hash(core)
        created = now_iso or utc_now()
        intent = ExecutionIntent(
            intent_id=iid,
            decision_id=decision_id,
            cycle_id=cycle_id,
            opportunity_id=opportunity_id,
            symbol=symbol,
            strategy_ref=strategy_ref,
            decision_status=decision_status,
            intent_action=action,
            intent_status=IntentStatus.VALID,  # provisional; validator decides
            created_at=created,
            content_hash=ch,
            evidence_refs=evidence_refs,
            provenance=build_exec_provenance(core),
            notes="paper_intent_only",
        )
        self._intent_cache[iid] = intent
        return intent
