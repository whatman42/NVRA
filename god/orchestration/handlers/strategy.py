"""Strategy handler — READ-ONLY regarding lifecycle (4G v1)."""

from __future__ import annotations

from typing import Any, Optional

from god.orchestration.models.context import CognitiveContext, CognitiveStage
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class StrategyHandler:
    """Inspect strategy evidence only. No promote/retire/switch."""

    name = "strategy"

    def __init__(self, strategy_registry: Any = None) -> None:
        self._registry = strategy_registry

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if event.event_type not in (EventType.VALIDATION, EventType.STRATEGY):
            return []
        context.current_stage = CognitiveStage.STRATEGY
        strategy_id = event.payload_ref.get("strategy_id")
        lifecycle = event.payload_ref.get("lifecycle_state")
        if self._registry is not None and strategy_id:
            try:
                s = self._registry.get(strategy_id)
                if s is not None:
                    lifecycle = getattr(s.lifecycle_state, "value", str(s.lifecycle_state))
                    strategy_id = s.strategy_id
            except Exception:
                pass
        if not strategy_id:
            strategy_id = f"strat-ref-{event.event_id[:8]}"
        context.evidence_index["strategy"] = str(strategy_id)
        if lifecycle:
            context.evidence_index["strategy_lifecycle"] = str(lifecycle)
        return [
            create_event(
                EventType.STRATEGY,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={
                    "strategy_id": str(strategy_id),
                    "lifecycle_state": str(lifecycle or "UNKNOWN"),
                    "read_only": True,
                },
            )
        ]
