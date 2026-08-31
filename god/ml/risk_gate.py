"""ML → risk gate. Prediction alone never becomes an order."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .prediction import Prediction, Direction


@dataclass(frozen=True)
class RiskGateDecision:
    allowed: bool
    reason: str
    prediction: Optional[Prediction] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "prediction": self.prediction.to_dict() if self.prediction else None,
        }


class MLRiskGate:
    """Independent of model quality theater — hard thresholds."""

    def __init__(
        self,
        *,
        min_probability: float = 0.55,
        min_confidence: float = 0.5,
        block_neutral: bool = True,
        kill_switch: bool = False,
    ) -> None:
        self.min_probability = min_probability
        self.min_confidence = min_confidence
        self.block_neutral = block_neutral
        self.kill_switch = kill_switch

    def evaluate(self, pred: Prediction) -> RiskGateDecision:
        if self.kill_switch:
            return RiskGateDecision(False, "kill_switch", pred)
        if self.block_neutral and pred.direction == Direction.NEUTRAL:
            return RiskGateDecision(False, "neutral_blocked", pred)
        if pred.probability < self.min_probability:
            return RiskGateDecision(False, "probability_below_min", pred)
        if pred.confidence < self.min_confidence:
            return RiskGateDecision(False, "confidence_below_min", pred)
        return RiskGateDecision(True, "pass", pred)
