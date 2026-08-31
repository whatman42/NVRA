"""MLEvidence handed to Market Decision Engine — one-way, no execution authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .prediction import Prediction, PredictionStatus


@dataclass(frozen=True)
class MLEvidence:
    prediction: Optional[Prediction]
    ml_gate_open: bool
    reasons: tuple[str, ...] = ()
    source: str = "god.ml"

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction": self.prediction.to_dict() if self.prediction else None,
            "ml_gate_open": self.ml_gate_open,
            "reasons": list(self.reasons),
            "source": self.source,
            "broker_orders_submitted": 0,
        }


def evidence_from_prediction(pred: Prediction, *, min_probability: float = 0.55) -> MLEvidence:
    reasons: list[str] = []
    if pred.status != PredictionStatus.VALID:
        reasons.append(f"status:{pred.status.value}")
    if pred.probability < min_probability and pred.direction.value != "NEUTRAL":
        reasons.append("probability_below_min")
    gate = pred.allows_entry_evidence and not reasons
    if not gate and not reasons:
        reasons.append("gate_closed")
    return MLEvidence(prediction=pred, ml_gate_open=gate, reasons=tuple(reasons))
