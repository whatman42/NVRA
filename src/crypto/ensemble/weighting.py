"""Bounded, normalized, auditable model weights."""

from __future__ import annotations

from dataclasses import dataclass

from crypto.ml.prediction import Regime


@dataclass(frozen=True, slots=True)
class WeightConfig:
    """Per-algorithm base weight and optional regime multipliers.

    All multipliers clamped; final weights always re-normalized to sum=1.
    """

    base: dict[str, float]
    # regime -> algorithm -> multiplier (default 1.0)
    regime_multipliers: dict[str, dict[str, float]] | None = None
    min_weight: float = 0.05
    max_weight: float = 0.70


DEFAULT_WEIGHTS = WeightConfig(
    base={
        "lightgbm": 1.0,
        "xgboost": 1.0,
        "random_forest": 0.9,
        "catboost": 0.9,
        "fallback": 0.4,
    },
    regime_multipliers={
        Regime.HIGH_VOLATILITY.name: {
            "random_forest": 1.2,
            "fallback": 0.8,
        },
        Regime.TREND_UP.name: {
            "lightgbm": 1.15,
            "xgboost": 1.1,
        },
        Regime.TREND_DOWN.name: {
            "lightgbm": 1.15,
            "xgboost": 1.1,
        },
        Regime.SIDEWAYS.name: {
            "random_forest": 1.1,
            "fallback": 1.0,
        },
    },
)


def compute_weights(
    algorithms: list[str],
    *,
    regime: Regime = Regime.UNKNOWN,
    metrics: dict[str, dict[str, float]] | None = None,
    config: WeightConfig | None = None,
) -> dict[str, float]:
    """Return normalized weights for the given algorithm set.

    metrics: optional algorithm -> {accuracy, ...} to nudge weights.
    """
    cfg = config or DEFAULT_WEIGHTS
    if not algorithms:
        return {}

    raw: dict[str, float] = {}
    reg_map = (cfg.regime_multipliers or {}).get(regime.name, {})
    for algo in algorithms:
        w = cfg.base.get(algo, 0.5)
        w *= reg_map.get(algo, 1.0)
        if metrics and algo in metrics:
            acc = metrics[algo].get("accuracy")
            if acc is not None:
                # mild nudge: accuracy 0.33 → 0.8x, 0.6 → 1.2x
                w *= max(0.5, min(1.3, 0.5 + float(acc)))
        w = max(cfg.min_weight, min(cfg.max_weight, w))
        raw[algo] = w

    total = sum(raw.values()) or 1.0
    return {k: v / total for k, v in raw.items()}
