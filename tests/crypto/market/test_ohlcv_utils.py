"""OHLCV validation and gap detection."""

from __future__ import annotations

import pytest

from crypto.exchanges.errors import MarketDataError
from crypto.exchanges.models import OHLCVBar
from crypto.market.ohlcv_utils import detect_gaps, validate_ohlcv_bar, validate_ohlcv_series
from crypto.market.quality import DataQuality


def _bar(
    ts: int,
    o: float = 100,
    h: float = 110,
    low: float = 90,
    c: float = 105,
    v: float = 1,
) -> OHLCVBar:
    return OHLCVBar(timestamp_ms=ts, open=o, high=h, low=low, close=c, volume=v)


def test_valid_bar() -> None:
    validate_ohlcv_bar(_bar(1_700_000_000_000))


def test_negative_volume() -> None:
    with pytest.raises(MarketDataError, match="volume"):
        validate_ohlcv_bar(_bar(1_700_000_000_000, v=-1))


def test_invalid_high_low() -> None:
    with pytest.raises(MarketDataError, match="high"):
        validate_ohlcv_bar(_bar(1_700_000_000_000, o=100, h=80, low=90, c=95))


def test_high_below_close() -> None:
    with pytest.raises(MarketDataError):
        validate_ohlcv_bar(_bar(1_700_000_000_000, o=100, h=100, low=90, c=105))


def test_zero_open() -> None:
    with pytest.raises(MarketDataError, match="open"):
        validate_ohlcv_bar(_bar(1_700_000_000_000, o=0))


def test_series_dedup_and_sort() -> None:
    bars = [
        _bar(1_700_000_120_000),
        _bar(1_700_000_000_000),
        _bar(1_700_000_000_000, h=1000, c=999),  # duplicate ts — last wins
    ]
    valid, invalid = validate_ohlcv_series(bars)
    assert invalid == 0
    assert len(valid) == 2
    assert valid[0].timestamp_ms == 1_700_000_000_000
    assert valid[0].close == 999


def test_series_drops_invalid() -> None:
    bars = [_bar(1_700_000_000_000), _bar(1_700_000_060_000, v=-5)]
    valid, invalid = validate_ohlcv_series(bars)
    assert len(valid) == 1
    assert invalid == 1


def test_gap_detection() -> None:
    # 1m bars with gap at +120s missing +60s
    t0 = 1_700_000_000_000
    bars = [_bar(t0), _bar(t0 + 60_000), _bar(t0 + 180_000)]
    missing, report = detect_gaps(bars, "1m")
    assert t0 + 120_000 in missing
    assert report.quality is DataQuality.GAP_DETECTED


def test_no_gap() -> None:
    t0 = 1_700_000_000_000
    bars = [_bar(t0), _bar(t0 + 60_000), _bar(t0 + 120_000)]
    missing, report = detect_gaps(bars, "1m")
    assert missing == []
    assert report.quality is DataQuality.COMPLETE
