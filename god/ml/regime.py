"""Market regime detection for regime-aware ML evaluation.

Regimes: TRENDING, RANGING, HIGH_VOLATILITY, LOW_VOLATILITY, UNCERTAIN.
Pure numpy; never uses future data. Fail-closed to UNCERTAIN on insufficient data.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

import numpy as np


class Regime(str, Enum):
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNCERTAIN = "UNCERTAIN"


@dataclass(frozen=True)
class RegimeSnapshot:
    regime: Regime
    trend_strength: float = 0.0
    volatility: float = 0.0
    vol_percentile: float = 0.5
    n_bars: int = 0
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "regime": self.regime.value,
            "trend_strength": self.trend_strength,
            "volatility": self.volatility,
            "vol_percentile": self.vol_percentile,
            "n_bars": self.n_bars,
            "reason": self.reason,
        }


def detect_regime(
    closes: Sequence[float] | np.ndarray,
    *,
    lookback: int = 48,
    min_bars: int = 20,
) -> RegimeSnapshot:
    """Detect current regime from price closes (chronological, no future leak).

    Uses last `lookback` bars only. Returns UNCERTAIN when data is thin.
    """
    arr = np.asarray(closes, dtype=float)
    if len(arr) < min_bars:
        return RegimeSnapshot(
            regime=Regime.UNCERTAIN,
            n_bars=len(arr),
            reason="insufficient_bars",
        )
    window = arr[-min(lookback, len(arr)) :]
    n = len(window)
    rets = np.diff(window) / np.clip(window[:-1], 1e-12, None)
    vol = float(np.std(rets)) if len(rets) > 1 else 0.0

    # Simple trend strength: absolute net move / path length
    net = abs(float(window[-1] - window[0]))
    path = float(np.sum(np.abs(np.diff(window)))) + 1e-12
    trend_strength = net / path

    # Volatility percentile vs expanding window of rolling std (causal)
    if len(rets) >= 10:
        roll = []
        for i in range(5, len(rets) + 1):
            roll.append(float(np.std(rets[max(0, i - 10) : i])))
        if roll:
            cur = roll[-1]
            vol_pct = float(np.mean(np.asarray(roll) <= cur))
        else:
            vol_pct = 0.5
            cur = vol
    else:
        vol_pct = 0.5
        cur = vol

    if vol_pct >= 0.85:
        regime = Regime.HIGH_VOLATILITY
        reason = "high_vol_percentile"
    elif vol_pct <= 0.20:
        regime = Regime.LOW_VOLATILITY
        reason = "low_vol_percentile"
    elif trend_strength >= 0.45:
        regime = Regime.TRENDING
        reason = "strong_directional_path"
    elif trend_strength <= 0.20:
        regime = Regime.RANGING
        reason = "mean_reverting_path"
    else:
        regime = Regime.UNCERTAIN
        reason = "mixed_signals"

    return RegimeSnapshot(
        regime=regime,
        trend_strength=float(trend_strength),
        volatility=float(cur),
        vol_percentile=float(vol_pct),
        n_bars=n,
        reason=reason,
    )


def regime_masks(
    closes: Sequence[float] | np.ndarray,
    *,
    lookback: int = 48,
    min_bars: int = 20,
) -> dict[Regime, np.ndarray]:
    """Per-bar causal regime labels (each index uses only past data)."""
    arr = np.asarray(closes, dtype=float)
    n = len(arr)
    labels = np.full(n, Regime.UNCERTAIN.value, dtype=object)
    for i in range(min_bars, n):
        snap = detect_regime(arr[: i + 1], lookback=lookback, min_bars=min_bars)
        labels[i] = snap.regime.value
    masks: dict[Regime, np.ndarray] = {}
    for r in Regime:
        masks[r] = labels == r.value
    return masks
