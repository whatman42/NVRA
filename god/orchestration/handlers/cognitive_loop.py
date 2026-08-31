"""Additive 4G handler — routes to CognitiveLoopEngine when injected.

Does not modify existing handler signatures or EventType enum.
Business logic stays in god.loop; this is a thin adapter.
"""

from __future__ import annotations

from typing import Any, Optional

from god.orchestration.models.context import CognitiveContext
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class CognitiveLoopHandler:
    """Optional handler: on OBSERVATION, run injected loop engine once."""

    name = "cognitive_loop"

    def __init__(self, loop_engine: Any = None) -> None:
        self._loop = loop_engine

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if self._loop is None:
            return []
        if event.event_type not in (EventType.OBSERVATION, EventType.SCHEDULER):
            return []
        try:
            result = self._loop.run_cycle()
        except Exception:
            return []
        context.evidence_index["cycle_id"] = result.cycle_id
        context.evidence_index["loop_status"] = result.status.value
        if result.attention:
            context.evidence_index["attention_set_id"] = result.attention.set_id
        # Use existing event types only — payload carries cycle refs
        return [
            create_event(
                EventType.POLICY,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={
                    "cycle_id": result.cycle_id,
                    "loop_status": result.status.value,
                    "discovery_result_id": result.discovery_result_id or "",
                    "selection_id": result.selection_id or "",
                    "attention_set_id": result.attention.set_id
                    if result.attention
                    else "",
                },
                notes="cognitive_loop_cycle_complete",
            )
        ]
