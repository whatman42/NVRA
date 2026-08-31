"""Research/experiment/validation handler — thin wrap of 4A/4B engines."""

from __future__ import annotations

from typing import Any

from god.orchestration.models.context import CognitiveContext, CognitiveStage
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class ResearchHandler:
    name = "research"

    def __init__(self, research_engine: Any = None, experiment_engine: Any = None) -> None:
        self._research = research_engine
        self._experiment = experiment_engine

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if event.event_type not in (
            EventType.RESEARCH,
            EventType.HYPOTHESIS,
            EventType.EXPERIMENT,
        ):
            return []
        out: list[CognitiveEvent] = []
        if event.event_type == EventType.RESEARCH:
            context.current_stage = CognitiveStage.HYPOTHESIS
            hyp_id = event.payload_ref.get("hypothesis_id") or f"hyp-{event.event_id[:8]}"
            context.evidence_index["hypothesis"] = str(hyp_id)
            out.append(
                create_event(
                    EventType.HYPOTHESIS,
                    correlation_id=event.correlation_id,
                    context_id=context.context_id,
                    parent_event_id=event.event_id,
                    payload_ref={"hypothesis_id": str(hyp_id)},
                )
            )
            context.current_stage = CognitiveStage.EXPERIMENT
            exp_id = f"exp-{event.event_id[:8]}"
            context.evidence_index["experiment"] = exp_id
            out.append(
                create_event(
                    EventType.EXPERIMENT,
                    correlation_id=event.correlation_id,
                    context_id=context.context_id,
                    parent_event_id=out[-1].event_id,
                    payload_ref={"experiment_id": exp_id, "hypothesis_id": str(hyp_id)},
                )
            )
            context.current_stage = CognitiveStage.VALIDATION
            out.append(
                create_event(
                    EventType.VALIDATION,
                    correlation_id=event.correlation_id,
                    context_id=context.context_id,
                    parent_event_id=out[-1].event_id,
                    payload_ref={"experiment_id": exp_id, "validation": "metadata_only"},
                )
            )
        return out
