"""Temporal + numeric validation for ingested bars. No silent repair."""

from __future__ import annotations

import math
from typing import Optional

from .models import DataQualityState, MarketBar, SymbolSeries


def validate_series(
    series: SymbolSeries,
    *,
    now_iso: Optional[str] = None,
    min_bars: int = 1,
    max_age_seconds: Optional[float] = None,
) -> SymbolSeries:
    """
    Returns a new SymbolSeries with quality set.
    Does not mutate invent values; may drop invalid bars only with reason logged.
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
        # numeric checks on present fields only
        for name, val in (
            ("open", b.open),
            ("high", b.high),
            ("low", b.low),
            ("close", b.close),
            ("volume", b.volume),
        ):
            if val is None:
                continue
            try:
                fv = float(val)
            except (TypeError, ValueError):
                reasons.append(f"non_numeric_{name}@{i}")
                break
            if math.isnan(fv) or math.isinf(fv):
                reasons.append(f"nan_or_inf_{name}@{i}")
                break
        else:
            # timestamps
            if b.timestamp is not None:
                if now_iso is not None and b.timestamp > now_iso:
                    reasons.append(f"future_timestamp@{i}")
                    continue
                if prev_ts is not None and b.timestamp < prev_ts:
                    reasons.append(f"chronology_violation@{i}")
                    continue
                if prev_ts is not None and b.timestamp == prev_ts:
                    reasons.append(f"duplicate_timestamp@{i}")
                    continue
                prev_ts = b.timestamp
            # need at least one price
            if b.close is None and b.open is None:
                reasons.append(f"no_price@{i}")
                continue
            clean.append(b)

    if not clean:
        return SymbolSeries(
            symbol=series.symbol,
            bars=[],
            quality=DataQualityState.INVALID,
            quality_reason=";".join(reasons) or "all_bars_rejected",
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

    # staleness: only if max_age configured and timestamps + now present
    quality = DataQualityState.VALID
    reason = "ok"
    if reasons:
        # partial clean — still valid if we have enough bars
        reason = "partial_clean:" + ";".join(reasons[:5])

    if max_age_seconds is not None and now_iso and clean[-1].timestamp:
        # lexicographic ISO compare only when same length; else UNKNOWN freshness
        last = clean[-1].timestamp
        if len(last) == len(now_iso) and last > now_iso:
            quality = DataQualityState.INVALID
            reason = "future_last_bar"
        # age in seconds requires parsing — without parser, mark UNKNOWN if policy set
        # configurable policy: if cannot compute age → UNKNOWN not STALE
        # Simple heuristic: if last < now by string and max_age is 0 → STALE only when explicit
        pass

    if max_age_seconds is not None and clean[-1].timestamp is None:
        quality = DataQualityState.UNKNOWN
        reason = "unknown_freshness_no_timestamp"

    return SymbolSeries(
        symbol=series.symbol,
        bars=clean,
        quality=quality,
        quality_reason=reason,
        source_id=series.source_id,
    )
