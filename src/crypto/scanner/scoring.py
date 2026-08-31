"""Bounded opportunity score composition."""

from __future__ import annotations

from crypto.ensemble.aggregate import EnsemblePrediction
from crypto.market.quality import DataQuality
from crypto.ml.prediction import Direction


def score_opportunity(
    ensemble: EnsemblePrediction | None,
    *,
    spread_pct: float | None,
    liquidity_score: float,
    available_quote: float,
    has_existing_exposure: bool,
    fee_pct: float,
    slippage_pct: float,
) -> float:
    """Compose 0..1 score. Explainable bounded components only."""
    if ensemble is None:
        return 0.0
    if ensemble.data_quality in (
        DataQuality.STALE,
        DataQuality.INVALID,
        DataQuality.UNKNOWN,
    ):
        return 0.0
    if ensemble.direction is Direction.NEUTRAL:
        return 0.0

    conf = max(0.0, min(1.0, ensemble.confidence))
    agree = max(0.0, min(1.0, ensemble.agreement))
    edge = max(0.0, min(1.0, abs(ensemble.expected_return) * 50.0))  # scale
    liq = max(0.0, min(1.0, liquidity_score))
    spread_pen = 0.0
    if spread_pct is not None:
        spread_pen = min(1.0, spread_pct / 2.0)  # 2% spread → full penalty

    cost = (fee_pct + slippage_pct) / 100.0
    cost_pen = min(1.0, cost * 20.0)

    score = (
        0.35 * conf + 0.25 * agree + 0.20 * edge + 0.10 * liq - 0.05 * spread_pen - 0.05 * cost_pen
    )
    if ensemble.high_disagreement:
        score *= 0.5
    if has_existing_exposure:
        score *= 0.7
    if available_quote <= 0 and ensemble.direction is Direction.UP:
        score *= 0.3  # want to buy but no quote

    return float(max(0.0, min(1.0, score)))
