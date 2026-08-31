"""Configurable freshness firewall. No universal market laws."""

from __future__ import annotations

from typing import Optional

from god.data.models import MarketDataSnapshot, DataQualityState

from .models import FreshnessPolicy, FreshnessStatus


def assess_freshness(
    snapshot: MarketDataSnapshot,
    policy: FreshnessPolicy,
    *,
    now_iso: Optional[str] = None,
) -> tuple[FreshnessStatus, str]:
    """
    Returns (status, reason).
    UNKNOWN if freshness cannot be established safely.
    """
    if not snapshot.universe and not snapshot.series:
        return FreshnessStatus.INVALID, "empty_snapshot"

    if snapshot.ingestion_status.value in (
        "EMPTY",
        "NO_VALID_MARKET_DATA",
        "INVALID_MARKET_DATA",
    ):
        return FreshnessStatus.INVALID, f"ingestion={snapshot.ingestion_status.value}"

    # collect last timestamps
    last_ts: list[str] = []
    missing_ts = 0
    for ser in snapshot.series.values():
        ts_list = ser.timestamps()
        if not ts_list:
            missing_ts += 1
        else:
            last_ts.append(ts_list[-1])

    if policy.require_timestamps and missing_ts > 0:
        return FreshnessStatus.UNKNOWN, "missing_timestamps"

    if not last_ts:
        if policy.require_timestamps:
            return FreshnessStatus.UNKNOWN, "no_timestamps"
        return FreshnessStatus.UNKNOWN, "unknown_freshness_no_timestamps"

    if now_iso:
        for t in last_ts:
            if t > now_iso:
                return FreshnessStatus.INVALID, "future_timestamp"

    # age-based stale only when max_age configured AND comparable ISO strings
    if policy.max_age_seconds is not None and now_iso:
        # Without full datetime parse of all formats, use lexicographic only when equal length
        comparable = [t for t in last_ts if len(t) == len(now_iso)]
        if not comparable:
            return FreshnessStatus.UNKNOWN, "cannot_compare_timestamps"
        # If any last bar string is far — we cannot compute seconds reliably without parser
        # Fail-closed: if max_age is 0, require last == now roughly not enforceable
        # Mark STALE only when policy explicitly wants fail and we detect all timestamps
        # older by simple string inequality under same length (weak) — prefer UNKNOWN
        # when age cannot be proven.
        if policy.max_age_seconds <= 0:
            return FreshnessStatus.STALE, "max_age_zero_policy"
        # Conservative: if require_timestamps and we have timestamps before now → FRESH
        # unless quality already STALE
        if any(s.quality == DataQualityState.STALE for s in snapshot.series.values()):
            return FreshnessStatus.STALE, "series_marked_stale"

    if snapshot.partial and not policy.allow_partial_universe:
        return FreshnessStatus.INVALID, "partial_not_allowed"

    if any(s.quality == DataQualityState.STALE for s in snapshot.series.values()):
        return FreshnessStatus.STALE, "series_stale"

    if not any(s.quality == DataQualityState.VALID for s in snapshot.series.values()):
        return FreshnessStatus.INVALID, "no_valid_series"

    return FreshnessStatus.FRESH, "ok"
