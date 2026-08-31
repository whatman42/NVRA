"""Curiosity handler — wraps CuriosityEngine / ResearchTrigger."""

from __future__ import annotations

from typing import Any, Optional

from god.orchestration.models.context import CognitiveContext, CognitiveStage
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class CuriosityHandler:
    name = "curiosity"

    def __init__(self, curiosity_engine: Any = None, research_trigger: Any = None) -> None:
        self._engine = curiosity_engine
        self._trigger = research_trigger

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if event.event_type not in (EventType.OBSERVATION, EventType.ANOMALY):
            return []
        context.current_stage = CognitiveStage.CURIOSITY
        out: list[CognitiveEvent] = []
        # If engine injected, call process; else pass-through synthetic curiosity ref
        curiosity_id = event.payload_ref.get("curiosity_event_id")
        if self._engine is not None and hasattr(self._engine, "process"):
            try:
                obs = event.payload_ref.get("observation") or {}
                results = self._engine.process(obs) if callable(self._engine.process) else []
                if results:
                    curiosity_id = getattr(results[0], "event_id", None) or str(results[0])
            except Exception:
                pass
        if not curiosity_id:
            curiosity_id = f"cur-ref-{event.event_id[:12]}"
        context.evidence_index["curiosity"] = str(curiosity_id)
        out.append(
            create_event(
                EventType.CURIOSITY,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={"curiosity_event_id": str(curiosity_id)},
            )
        )
        out.append(
            create_event(
                EventType.RESEARCH,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=out[-1].event_id,
                payload_ref={"from_curiosity": str(curiosity_id)},
            )
        )
        return out
