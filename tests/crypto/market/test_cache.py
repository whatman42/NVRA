"""Bounded cache behaviour."""

from __future__ import annotations

from crypto.exchanges.models import OHLCVBar, Ticker
from crypto.market.cache import BoundedCache, MarketDataCache


def test_bounded_eviction() -> None:
    c: BoundedCache[str, int] = BoundedCache(max_size=2, ttl_ms=0)
    c.put("a", 1)
    c.put("b", 2)
    c.put("c", 3)
    assert len(c) == 2
    assert c.get("a") is None  # evicted LRU
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_ttl_expiry() -> None:
    c: BoundedCache[str, int] = BoundedCache(max_size=10, ttl_ms=100)
    c.put("x", 1, now_ms=1000)
    assert c.get("x", now_ms=1050) == 1
    assert c.get("x", now_ms=1200) is None


def test_ohlcv_merge_dedup() -> None:
    cache = MarketDataCache(max_candles_per_key=10, ttl_ms=0)
    b1 = OHLCVBar(1000, 1, 2, 0.5, 1.5, 10)
    b2 = OHLCVBar(2000, 1.5, 2.5, 1, 2, 11)
    b1b = OHLCVBar(1000, 1.1, 2.1, 0.6, 1.6, 12)  # same ts
    cache.put_ohlcv("binance", "BTC/USDT", "1m", (b1, b2))
    merged = cache.merge_ohlcv("binance", "BTC/USDT", "1m", (b1b,))
    assert len(merged) == 2
    assert merged[0].close == 1.6


def test_candle_cap() -> None:
    cache = MarketDataCache(max_candles_per_key=3, ttl_ms=0)
    bars = tuple(OHLCVBar(i * 1000, 1, 2, 0.5, 1.5, 1) for i in range(10))
    cache.put_ohlcv("binance", "BTC/USDT", "1m", bars)
    got = cache.get_ohlcv("binance", "BTC/USDT", "1m")
    assert got is not None
    assert len(got) == 3
    assert got[0].timestamp_ms == 7_000  # kept most recent


def test_ticker_cache() -> None:
    cache = MarketDataCache(max_ticker=2, ttl_ms=0)
    t = Ticker(
        exchange="binance",
        symbol="BTC/USDT",
        timestamp_ms=1000,
        bid=1.0,
        ask=1.1,
        last=1.05,
        high=None,
        low=None,
        volume=None,
        quote_volume=None,
    )
    cache.put_ticker("binance", "BTC/USDT", t)
    assert cache.get_ticker("binance", "BTC/USDT") is t
