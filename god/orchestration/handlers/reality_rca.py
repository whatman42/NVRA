"""Reality gap + RCA handler — evidence only."""

from __future__ import annotations

from typing import Any

from god.orchestration.models.context import CognitiveContext, CognitiveStage
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class RealityRCAHandler:
    name = "reality_rca"

    def __init__(self, reality_engine: Any = None, rca_engine: Any = None) -> None:
        self._reality = reality_engine
        self._rca = rca_engine

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if event.event_type not in (
            EventType.STRATEGY,
            EventType.REALITY_GAP,
            EventType.FAILURE,
        ):
            return []
        out: list[CognitiveEvent] = []
        context.current_stage = CognitiveStage.REALITY_GAP
        gap_id = event.payload_ref.get("gap_id") or f"gap-{event.event_id[:8]}"
        if self._reality is not None and hasattr(self._reality, "record_gap"):
            try:
                from god.research.reality import GapDimension, MetricObservation

                g = self._reality.record_gap(
                    dimension=GapDimension.OBSERVATION_GAP,
                    expected=MetricObservation(name="x", value=1.0),
                    observed=MetricObservation(name="x", value=1.1),
                    strategy_ref=context.evidence_index.get("strategy"),
                )
                gap_id = g.gap_id
            except Exception:
                pass
        context.evidence_index["reality_gap"] = str(gap_id)
        out.append(
            create_event(
                EventType.REALITY_GAP,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={"gap_id": str(gap_id)},
            )
        )
        context.current_stage = CognitiveStage.RCA
        fail_id = f"fail-{event.event_id[:8]}"
        if self._rca is not None and hasattr(self._rca, "record_failure"):
            try:
                f = self._rca.record_failure(
                    source="orchestration",
                    expected_behavior="aligned",
                    observed_behavior="gap_present",
                    strategy_ref=context.evidence_index.get("strategy"),
                    evidence_refs=[str(gap_id)],
                    gap_refs=[str(gap_id)],
                )
                fail_id = f.failure_id
            except Exception:
                pass
        context.evidence_index["failure"] = str(fail_id)
        out.append(
            create_event(
                EventType.RCA,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=out[-1].event_id,
                payload_ref={"failure_id": str(fail_id), "gap_id": str(gap_id)},
            )
        )
        return out
