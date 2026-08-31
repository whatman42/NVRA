"""Policy + capital safety handler. ALLOW ≠ OPEN. No allocation."""

from __future__ import annotations

from typing import Any

from god.orchestration.models.context import CognitiveContext, CognitiveStage
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class PolicyCapitalHandler:
    name = "policy_capital"

    def __init__(self, policy_engine: Any = None, capital_engine: Any = None) -> None:
        self._policy = policy_engine
        self._capital = capital_engine

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if event.event_type not in (
            EventType.REGIME,
            EventType.DRIFT,
            EventType.POLICY,
            EventType.CAPITAL_SAFETY,
        ):
            return []
        out: list[CognitiveEvent] = []
        context.current_stage = CognitiveStage.POLICY
        permission = "UNKNOWN"
        decision_id = f"pol-{event.event_id[:8]}"
        if self._policy is not None:
            try:
                from god.policy import HealthFlag, PolicyEvidenceBundle

                bundle = PolicyEvidenceBundle(
                    system_health=HealthFlag.HEALTHY,
                    data_quality="VALID",
                    bridge_health=HealthFlag.HEALTHY,
                    execution_health=HealthFlag.HEALTHY,
                    reality_gap_refs=[context.evidence_index["reality_gap"]]
                    if "reality_gap" in context.evidence_index
                    else [],
                    rca_refs=[context.evidence_index["failure"]]
                    if "failure" in context.evidence_index
                    else [],
                    drift_refs=[context.evidence_index["drift"]]
                    if "drift" in context.evidence_index
                    else [],
                    strategy_lifecycle_state=context.evidence_index.get(
                        "strategy_lifecycle"
                    ),
                    uncertainty="LOW",
                )
                d = self._policy.evaluate(bundle)
                permission = d.permission.value
                decision_id = d.decision_id
            except Exception:
                permission = "UNKNOWN"
        context.evidence_index["policy_decision"] = decision_id
        context.evidence_index["permission"] = permission
        # CRITICAL: do NOT map permission to OPEN/BUY/SELL
        out.append(
            create_event(
                EventType.POLICY,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={
                    "decision_id": decision_id,
                    "permission": permission,
                },
            )
        )
        context.current_stage = CognitiveStage.CAPITAL_SAFETY
        capital_state = "UNKNOWN"
        if self._capital is not None and hasattr(self._capital, "apply_permission_hint"):
            try:
                rec = self._capital.apply_permission_hint(
                    permission, evidence_refs=[decision_id]
                )
                capital_state = rec.state.value
            except Exception:
                capital_state = "UNKNOWN"
        context.evidence_index["capital_state"] = capital_state
        out.append(
            create_event(
                EventType.CAPITAL_SAFETY,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=out[-1].event_id,
                payload_ref={
                    "capital_state": capital_state,
                    "permission": permission,
                },
            )
        )
        context.current_stage = CognitiveStage.COMPLETE
        return out
