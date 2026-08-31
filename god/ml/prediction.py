"""Prediction contract — decision support only. Invalid → NO_ENTRY, never forced BUY/SELL."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Direction(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


class PredictionStatus(str, Enum):
    VALID = "VALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    CALIBRATION_INVALID = "CALIBRATION_INVALID"
    STALE = "STALE"
    OUT_OF_DISTRIBUTION = "OUT_OF_DISTRIBUTION"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Prediction:
    model_id: str
    model_version: str
    timestamp: str
    symbol: str
    timeframe: str
    direction: Direction
    probability: float
    confidence: float
    features_version: str
    dataset_hash: str = ""
    horizon: int = 1
    expected_return: float = 0.0
    regime: str = "UNKNOWN"
    status: PredictionStatus = PredictionStatus.UNKNOWN
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def allows_entry_evidence(self) -> bool:
        return self.status == PredictionStatus.VALID and self.direction != Direction.NEUTRAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "direction": self.direction.value,
            "probability": self.probability,
            "confidence": self.confidence,
            "features_version": self.features_version,
            "dataset_hash": self.dataset_hash,
            "horizon": self.horizon,
            "expected_return": self.expected_return,
            "regime": self.regime,
            "status": self.status.value if isinstance(self.status, PredictionStatus) else str(self.status),
            "metadata": dict(self.metadata),
            "allows_entry_evidence": self.allows_entry_evidence,
        }
