"""Shadow simulation — pure / injected only. No live broker provider."""

from __future__ import annotations

from typing import Any, Optional

from god.orchestration.models.context import CognitiveContext
from god.orchestration.models.events import CognitiveEvent, EventType, create_event


def pure_shadow_metrics(
    expected: dict[str, float],
    noise: float = 0.0,
) -> dict[str, float]:
    """Deterministic offline sim: observed = expected * (1+noise)."""
    return {k: float(v) * (1.0 + noise) for k, v in expected.items()}


class ShadowHandler:
    name = "shadow"

    def __init__(self, reality_engine: Any = None) -> None:
        self._reality = reality_engine

    def handle(
        self, event: CognitiveEvent, context: CognitiveContext
    ) -> list[CognitiveEvent]:
        """Produce RealityGapEvent from injected expected metrics only."""
        expected = event.payload_ref.get("expected_metrics") or {"metric": 1.0}
        if not isinstance(expected, dict):
            expected = {"metric": 1.0}
        # ensure numeric
        exp_f = {str(k): float(v) for k, v in expected.items() if _is_num(v)}
        if not exp_f:
            exp_f = {"metric": 1.0}
        noise = float(event.payload_ref.get("noise") or 0.0)
        observed = pure_shadow_metrics(exp_f, noise=noise)
        gap_id = f"shadow-gap-{event.event_id[:8]}"
        if self._reality is not None:
            try:
                from god.research.reality import GapDimension, MetricObservation

                key = next(iter(exp_f))
                g = self._reality.record_gap(
                    dimension=GapDimension.SIMULATION_GAP,
                    expected=MetricObservation(name=key, value=exp_f[key]),
                    observed=MetricObservation(name=key, value=observed[key]),
                )
                gap_id = g.gap_id
            except Exception:
                pass
        context.evidence_index["shadow_gap"] = gap_id
        return [
            create_event(
                EventType.REALITY_GAP,
                correlation_id=event.correlation_id,
                context_id=context.context_id,
                parent_event_id=event.event_id,
                payload_ref={
                    "gap_id": gap_id,
                    "source": "shadow_pure",
                    "expected_keys": list(exp_f.keys()),
                },
            )
        ]


def _is_num(v: Any) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False
