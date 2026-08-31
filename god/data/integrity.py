"""Data integrity gate for N.U.N.G. — no silent repair."""

from __future__ import annotations

import math
from typing import Optional

from .models import DataQualityState, MarketBar, SymbolSeries


def _finite(v: Optional[float]) -> bool:
    if v is None:
        return True
    try:
        fv = float(v)
    except (TypeError, ValueError):
        return False
    return not (math.isnan(fv) or math.isinf(fv))


def validate_ohlc_bar(bar: MarketBar, index: int = 0) -> tuple[bool, str]:
    """OHLC consistency. Fail closed on violations."""
    for name, val in (
        ("open", bar.open),
        ("high", bar.high),
        ("low", bar.low),
        ("close", bar.close),
        ("volume", bar.volume),
    ):
        if val is not None and not _finite(val):
            return False, f"non_finite_{name}@{index}"

    o, h, l, c = bar.open, bar.high, bar.low, bar.close
    if h is not None and l is not None and h < l:
        return False, f"high_lt_low@{index}"
    if h is not None and o is not None and h < o:
        return False, f"high_lt_open@{index}"
    if h is not None and c is not None and h < c:
        return False, f"high_lt_close@{index}"
    if l is not None and o is not None and l > o:
        return False, f"low_gt_open@{index}"
    if l is not None and c is not None and l > c:
        return False, f"low_gt_close@{index}"
    if bar.volume is not None and bar.volume < 0:
        return False, f"negative_volume@{index}"
    if o is None and h is None and l is None and c is None:
        return False, f"no_price@{index}"
    return True, "ok"


def is_timezone_aware_iso(ts: str) -> bool:
    """Require Z or explicit offset — no naive local assumptions."""
    if not ts or not isinstance(ts, str):
        return False
    if ts.endswith("Z") or ts.endswith("z"):
        return True
    # +HH:MM or -HH:MM
    if len(ts) >= 6 and (ts[-6] in "+-") and ts[-3] == ":":
        return True
    if len(ts) >= 5 and (ts[-5] in "+-") and ts[-3] != ":":
        # +HHMM
        return True
    return False


def integrity_check_series(
    series: SymbolSeries,
    *,
    now_iso: Optional[str] = None,
    require_aware_timestamps: bool = True,
    min_bars: int = 1,
) -> SymbolSeries:
    """
    Full integrity pass. Returns new SymbolSeries with quality set.
    Does not invent or repair values.
    """
    if not series.bars:
        return SymbolSeries(
            symbol=series.symbol,
            bars=[],
            quality=DataQualityState.INSUFFICIENT,
            quality_reason="empty_series",
            source_id=series.source_id,
        )

    clean: list[MarketBar] = []
    reasons: list[str] = []
    prev_ts: Optional[str] = None

    for i, b in enumerate(series.bars):
        ok, reason = validate_ohlc_bar(b, i)
        if not ok:
            reasons.append(reason)
            continue

        if b.timestamp is not None:
            if require_aware_timestamps and not is_timezone_aware_iso(b.timestamp):
                reasons.append(f"naive_timestamp@{i}")
                continue
            if now_iso is not None and b.timestamp > now_iso:
                reasons.append(f"future_timestamp@{i}")
                continue
            if prev_ts is not None:
                if b.timestamp < prev_ts:
                    reasons.append(f"chronology_violation@{i}")
                    continue
                if b.timestamp == prev_ts:
                    reasons.append(f"duplicate_timestamp@{i}")
                    continue
            prev_ts = b.timestamp
        elif require_aware_timestamps:
            # missing timestamp when required → reject bar
            reasons.append(f"missing_timestamp@{i}")
            continue

        clean.append(b)

    if not clean:
        return SymbolSeries(
            symbol=series.symbol,
            bars=[],
            quality=DataQualityState.INVALID,
            quality_reason=";".join(reasons[:10]) or "all_rejected",
            source_id=series.source_id,
        )

    if len(clean) < min_bars:
        return SymbolSeries(
            symbol=series.symbol,
            bars=clean,
            quality=DataQualityState.INSUFFICIENT,
            quality_reason=f"bars={len(clean)}<min={min_bars}",
            source_id=series.source_id,
        )

    reason = "ok" if not reasons else "partial_clean:" + ";".join(reasons[:5])
    return SymbolSeries(
        symbol=series.symbol,
        bars=clean,
        quality=DataQualityState.VALID,
        quality_reason=reason,
        source_id=series.source_id,
    )
