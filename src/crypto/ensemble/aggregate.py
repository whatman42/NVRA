"""Ensemble aggregation from per-model votes."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass

from crypto.ensemble.weighting import WeightConfig, compute_weights
from crypto.market.quality import DataQuality
from crypto.ml.labels import int_to_direction
from crypto.ml.prediction import Direction, ModelVote, Prediction, Regime


@dataclass(frozen=True, slots=True)
class EnsemblePrediction:
    """Aggregated multi-model prediction — ranking signal only."""

    symbol: str
    direction: Direction
    probability: float
    confidence: float
    confidence_calibrated: bool
    agreement: float  # 0..1 fraction agreeing with ensemble direction
    disagreement: float  # 1 - agreement
    high_disagreement: bool
    expected_return: float
    volatility_estimate: float
    regime: Regime
    model_votes: tuple[ModelVote, ...]
    model_versions: tuple[str, ...]
    weights_used: dict[str, float]
    data_quality: DataQuality
    opportunity_score: float  # filled by scanner; ensemble may seed it
    feature_timestamp_ms: int
    generated_at_ms: int
    horizon_bars: int = 5

    def to_prediction(self) -> Prediction:
        """Down-convert for strategy bridge compatibility."""
        return Prediction(
            symbol=self.symbol,
            direction=self.direction,
            probability=self.probability,
            confidence=self.confidence,
            confidence_calibrated=self.confidence_calibrated,
            expected_return=self.expected_return,
            volatility_estimate=self.volatility_estimate,
            regime=self.regime,
            model_id="ensemble",
            algorithm="ensemble",
            feature_timestamp_ms=self.feature_timestamp_ms,
            generated_at_ms=self.generated_at_ms,
            data_quality=self.data_quality,
            votes=self.model_votes,
            horizon_bars=self.horizon_bars,
        )


def aggregate_votes(
    symbol: str,
    votes: Sequence[ModelVote],
    *,
    regime: Regime = Regime.UNKNOWN,
    data_quality: DataQuality = DataQuality.UNKNOWN,
    feature_timestamp_ms: int = 0,
    volatility: float = 0.0,
    metrics: dict[str, dict[str, float]] | None = None,
    weight_config: WeightConfig | None = None,
    disagreement_threshold: float = 0.4,
    horizon_bars: int = 5,
) -> EnsemblePrediction:
    """Weighted vote aggregation with explicit disagreement."""
    if not votes:
        now = int(time.time() * 1000)
        return EnsemblePrediction(
            symbol=symbol,
            direction=Direction.NEUTRAL,
            probability=0.0,
            confidence=0.0,
            confidence_calibrated=False,
            agreement=0.0,
            disagreement=1.0,
            high_disagreement=True,
            expected_return=0.0,
            volatility_estimate=volatility,
            regime=regime,
            model_votes=(),
            model_versions=(),
            weights_used={},
            data_quality=data_quality,
            opportunity_score=0.0,
            feature_timestamp_ms=feature_timestamp_ms,
            generated_at_ms=now,
            horizon_bars=horizon_bars,
        )

    algos = [v.algorithm for v in votes]
    weights = compute_weights(algos, regime=regime, metrics=metrics, config=weight_config)

    # Weighted class scores
    score = [0.0, 0.0, 0.0]  # down, neutral, up
    for v in votes:
        w = weights.get(v.algorithm, 0.0)
        score[0] += w * v.probability_down
        score[1] += w * v.probability_neutral
        score[2] += w * v.probability_up

    total = sum(score) or 1.0
    score = [s / total for s in score]
    pred_cls = max(range(3), key=lambda i: score[i])
    direction = int_to_direction(pred_cls)
    probability = score[pred_cls]

    # Agreement: weight mass on ensemble direction
    agree_mass = 0.0
    for v in votes:
        w = weights.get(v.algorithm, 0.0)
        # hard vote direction
        hard = max(
            (v.probability_down, Direction.DOWN),
            (v.probability_neutral, Direction.NEUTRAL),
            (v.probability_up, Direction.UP),
            key=lambda x: x[0],
        )[1]
        if hard is direction:
            agree_mass += w
    agreement = max(0.0, min(1.0, agree_mass))
    disagreement = 1.0 - agreement
    high_dis = disagreement >= disagreement_threshold

    ranked = sorted(score, reverse=True)
    margin = ranked[0] - ranked[1] if len(ranked) > 1 else ranked[0]
    confidence = max(0.0, min(1.0, margin * (1.0 - 0.5 * disagreement)))

    expected = (score[2] - score[0]) * 0.01
    versions = tuple(v.model_id for v in votes)
    now = int(time.time() * 1000)

    # Seed opportunity score (scanner will refine)
    seed = confidence * (1.0 - 0.3 * disagreement)
    if data_quality in (DataQuality.STALE, DataQuality.INVALID, DataQuality.UNKNOWN):
        seed = 0.0

    return EnsemblePrediction(
        symbol=symbol,
        direction=direction,
        probability=float(probability),
        confidence=float(confidence),
        confidence_calibrated=False,
        agreement=float(agreement),
        disagreement=float(disagreement),
        high_disagreement=high_dis,
        expected_return=float(expected),
        volatility_estimate=float(volatility),
        regime=regime,
        model_votes=tuple(votes),
        model_versions=versions,
        weights_used=dict(weights),
        data_quality=data_quality,
        opportunity_score=float(max(0.0, min(1.0, seed))),
        feature_timestamp_ms=feature_timestamp_ms,
        generated_at_ms=now,
        horizon_bars=horizon_bars,
    )
