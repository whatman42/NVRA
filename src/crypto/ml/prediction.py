"""Prediction outputs — signals only, never orders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from crypto.market.quality import DataQuality


class Direction(Enum):
    UP = auto()
    NEUTRAL = auto()
    DOWN = auto()


class Regime(Enum):
    TREND_UP = auto()
    TREND_DOWN = auto()
    SIDEWAYS = auto()
    HIGH_VOLATILITY = auto()
    LOW_VOLATILITY = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class ModelVote:
    """Per-model contribution (Phase 7 ensemble will aggregate these)."""

    model_id: str
    algorithm: str
    direction: Direction
    probability_up: float
    probability_down: float
    probability_neutral: float


@dataclass(frozen=True, slots=True)
class Prediction:
    """ML output handed to strategy — never to exchange APIs."""

    symbol: str
    direction: Direction
    probability: float  # P(primary direction)
    confidence: float  # calibrated or marked uncalibrated
    confidence_calibrated: bool
    expected_return: float
    volatility_estimate: float
    regime: Regime
    model_id: str
    algorithm: str
    feature_timestamp_ms: int
    generated_at_ms: int
    data_quality: DataQuality
    votes: tuple[ModelVote, ...] = ()
    horizon_bars: int = 5

    def is_actionable(self, min_confidence: float = 0.55) -> bool:
        if self.data_quality in (
            DataQuality.INVALID,
            DataQuality.STALE,
            DataQuality.UNKNOWN,
        ):
            return False
        if self.direction is Direction.NEUTRAL:
            return False
        return self.confidence >= min_confidence
