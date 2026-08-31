"""Lightweight tabular feature pipeline from OHLCV bars.

~20–40 features. No future leakage: row at index i uses only bars[0..i].
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from crypto.exchanges.models import OHLCVBar

# Stable feature schema version — bump when columns change
FEATURE_SCHEMA_VERSION = "v1"
FEATURE_NAMES: tuple[str, ...] = (
    # returns
    "ret_1",
    "ret_3",
    "ret_5",
    "ret_10",
    # momentum / trend
    "mom_5",
    "mom_10",
    "sma_ratio_5",
    "sma_ratio_20",
    "ema_gap",
    # volatility / range
    "vol_5",
    "vol_10",
    "atr_14",
    "range_pct",
    "body_pct",
    # volume
    "vol_chg_1",
    "vol_sma_ratio_5",
    "vol_sma_ratio_20",
    # RSI-like
    "rsi_14",
    # multi-bar context
    "hh_10",
    "ll_10",
    "close_location",
    # quality / structure
    "bar_count_norm",
)


@dataclass(frozen=True, slots=True)
class FeatureRow:
    timestamp_ms: int
    values: tuple[float, ...]  # aligned with FEATURE_NAMES

    def as_dict(self) -> dict[str, float]:
        return dict(zip(FEATURE_NAMES, self.values, strict=True))


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0.0 or math.isnan(b) or math.isinf(b):
        return default
    r = a / b
    if math.isnan(r) or math.isinf(r):
        return default
    return r


def _sma(closes: list[float], end: int, window: int) -> float:
    start = max(0, end - window + 1)
    seg = closes[start : end + 1]
    return sum(seg) / len(seg) if seg else 0.0


def _std(closes: list[float], end: int, window: int) -> float:
    start = max(0, end - window + 1)
    seg = closes[start : end + 1]
    if len(seg) < 2:
        return 0.0
    m = sum(seg) / len(seg)
    var = sum((x - m) ** 2 for x in seg) / (len(seg) - 1)
    return math.sqrt(max(0.0, var))


def _rsi(closes: list[float], end: int, window: int = 14) -> float:
    if end < 1:
        return 50.0
    start = max(1, end - window + 1)
    gains = 0.0
    losses = 0.0
    n = 0
    for i in range(start, end + 1):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
        n += 1
    if n == 0:
        return 50.0
    avg_gain = gains / n
    avg_loss = losses / n
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _atr(bars: Sequence[OHLCVBar], end: int, window: int = 14) -> float:
    start = max(1, end - window + 1)
    trs: list[float] = []
    for i in range(start, end + 1):
        h, low_px, pc = bars[i].high, bars[i].low, bars[i - 1].close
        tr = max(h - low_px, abs(h - pc), abs(low_px - pc))
        trs.append(tr)
    return sum(trs) / len(trs) if trs else 0.0


def compute_feature_row(bars: Sequence[OHLCVBar], index: int) -> FeatureRow:
    """Features for bar at `index` using only bars[0..index] (no future)."""
    if index < 0 or index >= len(bars):
        raise IndexError("feature index out of range")
    closes = [b.close for b in bars]
    volumes = [b.volume for b in bars]
    c = closes[index]
    bar = bars[index]

    def ret(n: int) -> float:
        j = index - n
        if j < 0 or closes[j] == 0:
            return 0.0
        return _safe_div(c - closes[j], closes[j])

    sma5 = _sma(closes, index, 5)
    sma20 = _sma(closes, index, 20)
    # simple EMA approximation
    ema = closes[0]
    alpha = 2.0 / (10 + 1)
    for i in range(1, index + 1):
        ema = alpha * closes[i] + (1 - alpha) * ema

    vol5 = _std(closes, index, 5)
    vol10 = _std(closes, index, 10)
    atr = _atr(bars, index, 14)
    rng = bar.high - bar.low
    body = abs(bar.close - bar.open)

    v_sma5 = _sma(volumes, index, 5)
    v_sma20 = _sma(volumes, index, 20)
    vol_chg = 0.0
    if index >= 1 and volumes[index - 1] > 0:
        vol_chg = _safe_div(volumes[index] - volumes[index - 1], volumes[index - 1])

    # highest high / lowest low over 10 (past only)
    start10 = max(0, index - 9)
    window_bars = bars[start10 : index + 1]
    hh = max(b.high for b in window_bars)
    ll = min(b.low for b in window_bars)

    values = (
        ret(1),
        ret(3),
        ret(5),
        ret(10),
        ret(5),  # mom_5 same as ret_5 scale
        ret(10),
        _safe_div(c, sma5, 1.0) - 1.0,
        _safe_div(c, sma20, 1.0) - 1.0,
        _safe_div(c - ema, c if c else 1.0),
        _safe_div(vol5, c if c else 1.0),
        _safe_div(vol10, c if c else 1.0),
        _safe_div(atr, c if c else 1.0),
        _safe_div(rng, c if c else 1.0),
        _safe_div(body, rng if rng else 1.0),
        vol_chg,
        _safe_div(volumes[index], v_sma5 if v_sma5 else 1.0) - 1.0,
        _safe_div(volumes[index], v_sma20 if v_sma20 else 1.0) - 1.0,
        _rsi(closes, index, 14) / 100.0,
        _safe_div(c, hh if hh else 1.0),
        _safe_div(c, ll if ll else 1.0) - 1.0 if ll else 0.0,
        _safe_div(c - bar.low, rng if rng else 1.0),
        min(1.0, (index + 1) / 100.0),
    )
    # Sanitize
    clean = tuple(0.0 if (math.isnan(v) or math.isinf(v)) else float(v) for v in values)
    return FeatureRow(timestamp_ms=bar.timestamp_ms, values=clean)


def build_feature_matrix(
    bars: Sequence[OHLCVBar],
    *,
    min_history: int = 20,
    max_rows: int | None = None,
) -> tuple[list[FeatureRow], list[int]]:
    """Return feature rows and their bar indices. Chronological order preserved."""
    rows: list[FeatureRow] = []
    indices: list[int] = []
    start = min_history
    end = len(bars)
    if max_rows is not None and end - start > max_rows:
        start = end - max_rows
        start = max(start, min_history)
    for i in range(start, end):
        rows.append(compute_feature_row(bars, i))
        indices.append(i)
    return rows, indices


def select_features(
    row: FeatureRow, names: Sequence[str] | None, max_features: int
) -> tuple[tuple[str, ...], tuple[float, ...]]:
    """Bound feature count per resource profile."""
    names = FEATURE_NAMES[:max_features] if names is None else tuple(names)[:max_features]
    idx = {n: i for i, n in enumerate(FEATURE_NAMES)}
    vals = tuple(row.values[idx[n]] for n in names if n in idx)
    used = tuple(n for n in names if n in idx)
    return used, vals
