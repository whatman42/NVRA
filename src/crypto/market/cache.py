"""Bounded in-memory market-data cache.

Designed for low-RAM hardware: every structure has a hard capacity limit
and TTL-based eviction. No unbounded growth.
"""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Generic, TypeVar

from crypto.exchanges.models import OHLCVBar, OrderBook, Ticker
from crypto.market.timeutils import utc_now_ms

K = TypeVar("K")
V = TypeVar("V")


@dataclass(slots=True)
class _Entry(Generic[V]):
    value: V
    stored_at_ms: int


class BoundedCache(Generic[K, V]):
    """Simple LRU + TTL cache with fixed capacity."""

    def __init__(self, max_size: int, ttl_ms: int) -> None:
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        self._max_size = max_size
        self._ttl_ms = ttl_ms
        self._data: OrderedDict[K, _Entry[V]] = OrderedDict()
        self.hits = 0
        self.misses = 0

    def get(self, key: K, *, now_ms: int | None = None) -> V | None:
        now = now_ms if now_ms is not None else utc_now_ms()
        entry = self._data.get(key)
        if entry is None:
            self.misses += 1
            return None
        if self._ttl_ms > 0 and (now - entry.stored_at_ms) > self._ttl_ms:
            del self._data[key]
            self.misses += 1
            return None
        self._data.move_to_end(key)
        self.hits += 1
        return entry.value

    def put(self, key: K, value: V, *, now_ms: int | None = None) -> None:
        now = now_ms if now_ms is not None else utc_now_ms()
        if key in self._data:
            del self._data[key]
        self._data[key] = _Entry(value=value, stored_at_ms=now)
        while len(self._data) > self._max_size:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        self._data.clear()


@dataclass(frozen=True, slots=True)
class OhlcvKey:
    exchange_id: str
    symbol: str
    timeframe: str


class MarketDataCache:
    """Composite bounded cache for ticker, OHLCV, and order book."""

    def __init__(
        self,
        *,
        max_ticker: int = 50,
        max_orderbook: int = 30,
        max_ohlcv_keys: int = 40,
        max_candles_per_key: int = 500,
        ttl_ms: int = 300_000,
    ) -> None:
        self._tickers: BoundedCache[tuple[str, str], Ticker] = BoundedCache(max_ticker, ttl_ms)
        self._orderbooks: BoundedCache[tuple[str, str], OrderBook] = BoundedCache(
            max_orderbook, ttl_ms
        )
        self._ohlcv: BoundedCache[OhlcvKey, tuple[OHLCVBar, ...]] = BoundedCache(
            max_ohlcv_keys, ttl_ms
        )
        self._max_candles = max_candles_per_key

    # --- ticker ---

    def get_ticker(
        self, exchange_id: str, symbol: str, *, now_ms: int | None = None
    ) -> Ticker | None:
        return self._tickers.get((exchange_id, symbol), now_ms=now_ms)

    def put_ticker(
        self, exchange_id: str, symbol: str, ticker: Ticker, *, now_ms: int | None = None
    ) -> None:
        self._tickers.put((exchange_id, symbol), ticker, now_ms=now_ms)

    # --- order book ---

    def get_orderbook(
        self, exchange_id: str, symbol: str, *, now_ms: int | None = None
    ) -> OrderBook | None:
        return self._orderbooks.get((exchange_id, symbol), now_ms=now_ms)

    def put_orderbook(
        self,
        exchange_id: str,
        symbol: str,
        book: OrderBook,
        *,
        now_ms: int | None = None,
    ) -> None:
        self._orderbooks.put((exchange_id, symbol), book, now_ms=now_ms)

    # --- OHLCV ---

    def get_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        *,
        now_ms: int | None = None,
    ) -> tuple[OHLCVBar, ...] | None:
        key = OhlcvKey(exchange_id, symbol, timeframe)
        return self._ohlcv.get(key, now_ms=now_ms)

    def put_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        bars: tuple[OHLCVBar, ...],
        *,
        now_ms: int | None = None,
    ) -> None:
        # Enforce per-key candle bound (keep most recent)
        if len(bars) > self._max_candles:
            bars = bars[-self._max_candles :]
        key = OhlcvKey(exchange_id, symbol, timeframe)
        self._ohlcv.put(key, bars, now_ms=now_ms)

    def merge_ohlcv(
        self,
        exchange_id: str,
        symbol: str,
        timeframe: str,
        new_bars: tuple[OHLCVBar, ...],
        *,
        now_ms: int | None = None,
    ) -> tuple[OHLCVBar, ...]:
        """Merge new bars into cache idempotently (by timestamp)."""
        existing = self.get_ohlcv(exchange_id, symbol, timeframe, now_ms=now_ms) or ()
        by_ts: dict[int, OHLCVBar] = {b.timestamp_ms: b for b in existing}
        for b in new_bars:
            by_ts[b.timestamp_ms] = b  # overwrite duplicates
        merged = tuple(sorted(by_ts.values(), key=lambda x: x.timestamp_ms))
        if len(merged) > self._max_candles:
            merged = merged[-self._max_candles :]
        self.put_ohlcv(exchange_id, symbol, timeframe, merged, now_ms=now_ms)
        return merged

    @property
    def stats(self) -> dict[str, int]:
        return {
            "ticker_size": len(self._tickers),
            "orderbook_size": len(self._orderbooks),
            "ohlcv_keys": len(self._ohlcv),
            "ticker_hits": self._tickers.hits,
            "ticker_misses": self._tickers.misses,
            "orderbook_hits": self._orderbooks.hits,
            "orderbook_misses": self._orderbooks.misses,
            "ohlcv_hits": self._ohlcv.hits,
            "ohlcv_misses": self._ohlcv.misses,
        }

    def clear(self) -> None:
        self._tickers.clear()
        self._orderbooks.clear()
        self._ohlcv.clear()
