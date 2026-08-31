"""Ensemble weighting, disagreement, aggregation."""

from __future__ import annotations

from crypto.ensemble import aggregate_votes, compute_weights
from crypto.market.quality import DataQuality
from crypto.ml.prediction import Direction, ModelVote, Regime


def _vote(algo: str, direction: Direction, up: float, down: float, neu: float) -> ModelVote:
    return ModelVote(
        model_id=f"m-{algo}",
        algorithm=algo,
        direction=direction,
        probability_up=up,
        probability_down=down,
        probability_neutral=neu,
    )


def test_weights_normalized() -> None:
    w = compute_weights(["lightgbm", "xgboost", "fallback"], regime=Regime.SIDEWAYS)
    assert abs(sum(w.values()) - 1.0) < 1e-6
    assert all(0.0 < v <= 0.70 for v in w.values())


def test_agreement() -> None:
    votes = [
        _vote("lightgbm", Direction.UP, 0.8, 0.1, 0.1),
        _vote("xgboost", Direction.UP, 0.7, 0.15, 0.15),
        _vote("random_forest", Direction.UP, 0.6, 0.2, 0.2),
    ]
    ep = aggregate_votes("BTC/USDT", votes, data_quality=DataQuality.COMPLETE)
    assert ep.direction is Direction.UP
    assert ep.agreement > 0.8
    assert not ep.high_disagreement


def test_strong_disagreement() -> None:
    votes = [
        _vote("lightgbm", Direction.UP, 0.85, 0.1, 0.05),
        _vote("xgboost", Direction.DOWN, 0.1, 0.8, 0.1),
        _vote("random_forest", Direction.NEUTRAL, 0.2, 0.2, 0.6),
    ]
    ep = aggregate_votes("BTC/USDT", votes, data_quality=DataQuality.COMPLETE)
    assert ep.disagreement > 0.3
    assert ep.confidence < 0.9


def test_empty_votes() -> None:
    ep = aggregate_votes("ETH/USDT", (), data_quality=DataQuality.STALE)
    assert ep.direction is Direction.NEUTRAL
    assert ep.opportunity_score == 0.0
