"""Drift / regime handler — observational evidence only."""

from __future__ import annotations

from typing import Any

from god.orchestration.models.context import CognitiveContext, CognitiveStage
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


class DriftRegimeHandler:
    name = "drift_regime"

    def __init__(self, drift_engine: Any = None, regime_engine: Any = None) -> None:
        self._drift = drift_engine
        self._regime = regime_engine

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        if event.event_type not in (EventType.RCA, EventType.DRIFT, EventType.REGIME):
            return []
        out: list[CognitiveEvent] = []
        context.current_stage = CognitiveStage.DRIFT
        drift_id = event.payload_ref.get("drift_id") or f"drift-{event.event_id[:8]}"
        if self._drift is not None:
            try:
                from god.research.drift import ObservationSeries

                a = self._drift.assess(
                    ObservationSeries(name="x", values=(1.0, 2.0, 3.0)),
                    ObservationSeries(name="x", values=(1.1, 2.1, 3.1)),
                )
                drift_id = a.assessment_id
            except Exception:
                pass
        context.evidence_index["drift"] = str(drift_id)
        out.append(
            create_event(
                EventType.DRIFT,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={"drift_id": str(drift_id)},
            )
        )
        context.current_stage = CognitiveStage.REGIME
        regime_id = f"regime-{event.event_id[:8]}"
        if self._regime is not None:
            try:
                from god.research.drift import ObservationSeries

                r = self._regime.classify(
                    ObservationSeries(name="p", values=(1.0, 1.1, 0.9, 1.0, 1.05))
                )
                regime_id = r.regime_id
            except Exception:
                pass
        context.evidence_index["regime"] = str(regime_id)
        out.append(
            create_event(
                EventType.REGIME,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=out[-1].event_id,
                payload_ref={"regime_id": str(regime_id)},
            )
        )
        return out
