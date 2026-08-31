"""Lightweight rule-based market regime (no second ML model)."""

from __future__ import annotations

from collections.abc import Sequence

from crypto.exchanges.models import OHLCVBar
from crypto.ml.prediction import Regime


def detect_regime(bars: Sequence[OHLCVBar], lookback: int = 20) -> Regime:
    if len(bars) < 5:
        return Regime.UNKNOWN
    window = bars[-lookback:] if len(bars) >= lookback else bars
    closes = [b.close for b in window]
    if closes[0] == 0:
        return Regime.UNKNOWN
    ret = (closes[-1] - closes[0]) / closes[0]
    # volatility proxy
    rets = []
    for i in range(1, len(closes)):
        if closes[i - 1] != 0:
            rets.append(abs((closes[i] - closes[i - 1]) / closes[i - 1]))
    vol = sum(rets) / len(rets) if rets else 0.0

    if vol > 0.02:
        return Regime.HIGH_VOLATILITY
    if vol < 0.003:
        return Regime.LOW_VOLATILITY
    if ret > 0.01:
        return Regime.TREND_UP
    if ret < -0.01:
        return Regime.TREND_DOWN
    return Regime.SIDEWAYS
