"""Symbol normalization and UTC time helpers."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from crypto.market.symbols import normalize_symbol
from crypto.market.timeutils import (
    ensure_utc_ms,
    is_future,
    is_stale,
    timeframe_to_ms,
    utc_now_ms,
)


def test_normalize_slash() -> None:
    ns = normalize_symbol("binance", "btc/usdt")
    assert ns.symbol == "BTC/USDT"
    assert ns.base == "BTC"
    assert ns.quote == "USDT"
    assert ns.native == "btc/usdt"


def test_normalize_with_metadata() -> None:
    ns = normalize_symbol("indodax", "btc_idr", base="btc", quote="idr")
    assert ns.symbol == "BTC/IDR"


def test_normalize_hyphen() -> None:
    ns = normalize_symbol("binance", "ETH-USDT")
    assert ns.symbol == "ETH/USDT"


def test_normalize_invalid() -> None:
    with pytest.raises(ValueError):
        normalize_symbol("binance", "!!!")


def test_timeframe_to_ms() -> None:
    assert timeframe_to_ms("1m") == 60_000
    assert timeframe_to_ms("5m") == 300_000
    assert timeframe_to_ms("1h") == 3_600_000
    assert timeframe_to_ms("4h") == 14_400_000


def test_timeframe_invalid() -> None:
    with pytest.raises(ValueError):
        timeframe_to_ms("1x")


def test_ensure_utc_ms_datetime() -> None:
    dt = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    assert ensure_utc_ms(dt) == 1_704_067_200_000


def test_is_stale() -> None:
    now = 1_000_000
    assert is_stale(now - 100, 50, now_ms=now) is True
    assert is_stale(now - 10, 50, now_ms=now) is False
    assert is_stale(None, 50, now_ms=now) is True


def test_is_future() -> None:
    now = utc_now_ms()
    assert is_future(now + 120_000, now_ms=now, tolerance_ms=60_000) is True
    assert is_future(now + 10_000, now_ms=now, tolerance_ms=60_000) is False
