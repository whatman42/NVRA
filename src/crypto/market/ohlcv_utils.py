"""OHLCV validation and gap detection."""

from __future__ import annotations

from crypto.exchanges.errors import MarketDataError
from crypto.exchanges.models import OHLCVBar
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.market.timeutils import is_future, timeframe_to_ms, utc_now_ms


def validate_ohlcv_bar(bar: OHLCVBar, *, now_ms: int | None = None) -> None:
    """Raise MarketDataError if a single bar is structurally invalid."""
    now = now_ms if now_ms is not None else utc_now_ms()
    if bar.timestamp_ms < 0:
        raise MarketDataError(f"invalid timestamp: {bar.timestamp_ms}")
    if is_future(bar.timestamp_ms, now_ms=now):
        raise MarketDataError(f"future timestamp: {bar.timestamp_ms}")
    for name, val in (
        ("open", bar.open),
        ("high", bar.high),
        ("low", bar.low),
        ("close", bar.close),
    ):
        if val <= 0:
            raise MarketDataError(f"{name} must be > 0, got {val}")
    if bar.volume < 0:
        raise MarketDataError(f"volume must be >= 0, got {bar.volume}")
    if bar.high < bar.low:
        raise MarketDataError(f"high {bar.high} < low {bar.low}")
    if bar.high < max(bar.open, bar.close):
        raise MarketDataError(f"high {bar.high} < max(open, close)={max(bar.open, bar.close)}")
    if bar.low > min(bar.open, bar.close):
        raise MarketDataError(f"low {bar.low} > min(open, close)={min(bar.open, bar.close)}")


def validate_ohlcv_series(
    bars: list[OHLCVBar] | tuple[OHLCVBar, ...],
    *,
    now_ms: int | None = None,
) -> tuple[list[OHLCVBar], int]:
    """Validate series; return (valid_bars, invalid_count).

    Duplicates (same timestamp) keep the last occurrence.
    Out-of-order input is sorted by timestamp after validation.
    """
    now = now_ms if now_ms is not None else utc_now_ms()
    by_ts: dict[int, OHLCVBar] = {}
    invalid = 0
    for bar in bars:
        try:
            validate_ohlcv_bar(bar, now_ms=now)
        except MarketDataError:
            invalid += 1
            continue
        by_ts[bar.timestamp_ms] = bar
    ordered = sorted(by_ts.values(), key=lambda b: b.timestamp_ms)
    return ordered, invalid


def detect_gaps(
    bars: list[OHLCVBar] | tuple[OHLCVBar, ...],
    timeframe: str,
) -> tuple[list[int], DataQualityReport]:
    """Detect missing candles. Does NOT invent fill values.

    Returns (missing_timestamps_ms, quality_report).
    """
    if not bars:
        return [], DataQualityReport(quality=DataQuality.UNKNOWN, reasons=("empty series",))

    interval = timeframe_to_ms(timeframe)
    missing: list[int] = []
    duplicate_count = 0
    prev_ts: int | None = None

    for bar in bars:
        if prev_ts is not None:
            expected = prev_ts + interval
            if bar.timestamp_ms == prev_ts:
                duplicate_count += 1
            elif bar.timestamp_ms > expected:
                t = expected
                while t < bar.timestamp_ms:
                    missing.append(t)
                    t += interval
        prev_ts = bar.timestamp_ms

    reasons: list[str] = []
    if missing:
        reasons.append(f"{len(missing)} gap(s) detected")
        quality = DataQuality.GAP_DETECTED
    elif duplicate_count:
        reasons.append(f"{duplicate_count} duplicate timestamp(s) collapsed")
        quality = DataQuality.PARTIAL
    else:
        quality = DataQuality.COMPLETE

    return missing, DataQualityReport(
        quality=quality,
        reasons=tuple(reasons),
        missing_timestamps_ms=tuple(missing),
        duplicate_count=duplicate_count,
    )
