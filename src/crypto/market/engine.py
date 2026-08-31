"""Market Data Engine — exchange-agnostic, read-only.

Sits on top of ExchangeAdapter. Provides validated, normalized, cached
market data to future Portfolio / Risk / ML / GUI consumers.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass

from crypto.exchanges.base import ExchangeAdapter
from crypto.exchanges.errors import (
    ExchangeError,
    MarketDataError,
    RateLimitError,
)
from crypto.exchanges.models import (
    AssetBalance,
    ConnectionHealth,
    Market,
    OHLCVBar,
    OrderBook,
    Ticker,
)
from crypto.market.cache import MarketDataCache
from crypto.market.config import MarketDataConfig
from crypto.market.ohlcv_utils import detect_gaps, validate_ohlcv_series
from crypto.market.quality import DataQuality, DataQualityReport, MarketDataMetrics
from crypto.market.symbols import NormalizedSymbol, normalize_symbol
from crypto.market.timeutils import (
    is_stale,
    timeframe_to_ms,
    utc_now_ms,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TickerSnapshot:
    ticker: Ticker
    symbol: NormalizedSymbol
    quality: DataQualityReport
    fetched_at_ms: int


@dataclass(frozen=True, slots=True)
class OHLCVSnapshot:
    bars: tuple[OHLCVBar, ...]
    symbol: NormalizedSymbol
    timeframe: str
    quality: DataQualityReport
    fetched_at_ms: int


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    book: OrderBook
    symbol: NormalizedSymbol
    quality: DataQualityReport
    fetched_at_ms: int


class MarketDataEngine:
    """Read-only market data facade over one ExchangeAdapter.

    Multi-exchange support is achieved by creating one engine per adapter
    (or a thin multi-engine coordinator later). Consumers never import CCXT.
    """

    def __init__(
        self,
        adapter: ExchangeAdapter,
        config: MarketDataConfig | None = None,
    ) -> None:
        self._adapter = adapter
        self._config = config or MarketDataConfig()
        self._config.validate()
        self._cache = MarketDataCache(
            max_ticker=self._config.max_ticker_entries,
            max_orderbook=self._config.max_orderbook_entries,
            max_ohlcv_keys=max(1, self._config.max_symbols * len(self._config.timeframes)),
            max_candles_per_key=self._config.max_candles_per_key,
            ttl_ms=self._config.cache_ttl_ms,
        )
        self._metrics = MarketDataMetrics()
        self._last_poll_ms: dict[str, int] = {}
        self._symbol_map: dict[str, NormalizedSymbol] = {}  # native -> normalized

    @property
    def exchange_id(self) -> str:
        return self._adapter.exchange_id

    @property
    def metrics(self) -> MarketDataMetrics:
        return self._metrics

    @property
    def config(self) -> MarketDataConfig:
        return self._config

    def connect(self) -> None:
        self._adapter.connect()

    def disconnect(self) -> None:
        self._adapter.disconnect()

    def health(self) -> ConnectionHealth:
        return self._adapter.health_check()

    # ------------------------------------------------------------------
    # Markets / symbols
    # ------------------------------------------------------------------

    def load_markets(self) -> Sequence[Market]:
        markets = self._adapter.fetch_markets()
        self._symbol_map.clear()
        for m in markets:
            try:
                ns = normalize_symbol(
                    self.exchange_id,
                    m.symbol,
                    base=m.base_asset or None,
                    quote=m.quote_asset or None,
                )
                self._symbol_map[m.symbol] = ns
            except ValueError:
                logger.debug("skip unnormalizable market %s", m.symbol)
        return markets

    def resolve_symbol(self, symbol: str) -> NormalizedSymbol:
        """Resolve a user-facing or native symbol to NormalizedSymbol."""
        if symbol in self._symbol_map:
            return self._symbol_map[symbol]
        # Try normalized form lookup
        for ns in self._symbol_map.values():
            if ns.symbol == symbol.upper() or ns.symbol == symbol:
                return ns
        # Best-effort parse
        return normalize_symbol(self.exchange_id, symbol)

    def _native_for(self, symbol: str) -> str:
        """Return exchange-native symbol string for adapter calls."""
        ns = self.resolve_symbol(symbol)
        return ns.native if ns.native else ns.symbol

    # ------------------------------------------------------------------
    # Ticker
    # ------------------------------------------------------------------

    def get_ticker(
        self,
        symbol: str,
        *,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> TickerSnapshot:
        now = utc_now_ms()
        ns = self.resolve_symbol(symbol)
        native = self._native_for(symbol)

        if use_cache and not force_refresh:
            cached = self._cache.get_ticker(self.exchange_id, ns.symbol, now_ms=now)
            if cached is not None:
                self._metrics.cache_hits += 1
                age = (now - (cached.timestamp_ms or now)) if cached.timestamp_ms else None
                quality = self._ticker_quality(cached, now)
                self._metrics.ticker_age_ms = age
                return TickerSnapshot(ticker=cached, symbol=ns, quality=quality, fetched_at_ms=now)
            self._metrics.cache_misses += 1

        self._throttle("ticker")
        try:
            raw = self._adapter.fetch_ticker(native)
        except RateLimitError:
            self._metrics.rate_limit_events += 1
            self._metrics.request_failures += 1
            raise
        except ExchangeError:
            self._metrics.request_failures += 1
            raise

        # Validate via existing Phase 2 guarantees + freshness
        quality = self._ticker_quality(raw, now)
        if quality.quality is DataQuality.INVALID:
            self._metrics.invalid_count += 1
            raise MarketDataError(
                f"invalid ticker for {ns.symbol}: {quality.reasons}",
                exchange_id=self.exchange_id,
            )

        self._cache.put_ticker(self.exchange_id, ns.symbol, raw, now_ms=now)
        self._metrics.last_ticker_update_ms = now
        self._metrics.ticker_age_ms = now - raw.timestamp_ms if raw.timestamp_ms is not None else 0
        return TickerSnapshot(ticker=raw, symbol=ns, quality=quality, fetched_at_ms=now)

    def _ticker_quality(self, ticker: Ticker, now_ms: int) -> DataQualityReport:
        reasons: list[str] = []
        if ticker.last is not None and ticker.last <= 0:
            return DataQualityReport(
                quality=DataQuality.INVALID, reasons=("non-positive last price",)
            )
        if ticker.bid is not None and ticker.ask is not None and ticker.bid > ticker.ask:
            return DataQualityReport(quality=DataQuality.INVALID, reasons=("crossed bid/ask",))
        if is_stale(
            ticker.timestamp_ms,
            self._config.ticker_stale_ms,
            now_ms=now_ms,
        ):
            reasons.append("stale ticker")
            return DataQualityReport(quality=DataQuality.STALE, reasons=tuple(reasons))
        return DataQualityReport(quality=DataQuality.COMPLETE)

    # ------------------------------------------------------------------
    # OHLCV
    # ------------------------------------------------------------------

    def get_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1m",
        *,
        limit: int | None = None,
        since_ms: int | None = None,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> OHLCVSnapshot:
        now = utc_now_ms()
        ns = self.resolve_symbol(symbol)
        native = self._native_for(symbol)
        lim = limit if limit is not None else self._config.default_ohlcv_limit

        if use_cache and not force_refresh and since_ms is None:
            cached = self._cache.get_ohlcv(self.exchange_id, ns.symbol, timeframe, now_ms=now)
            if cached is not None and len(cached) > 0:
                self._metrics.cache_hits += 1
                missing, gap_report = detect_gaps(cached, timeframe)
                quality = self._ohlcv_freshness(cached, timeframe, gap_report, now)
                self._metrics.missing_candles = len(missing)
                self._metrics.ohlcv_age_ms = now - cached[-1].timestamp_ms if cached else None
                return OHLCVSnapshot(
                    bars=cached,
                    symbol=ns,
                    timeframe=timeframe,
                    quality=quality,
                    fetched_at_ms=now,
                )
            self._metrics.cache_misses += 1

        self._throttle(f"ohlcv:{timeframe}")
        try:
            raw_bars = list(
                self._adapter.fetch_ohlcv(native, timeframe=timeframe, since_ms=since_ms, limit=lim)
            )
        except RateLimitError:
            self._metrics.rate_limit_events += 1
            self._metrics.request_failures += 1
            raise
        except ExchangeError:
            self._metrics.request_failures += 1
            raise

        valid, invalid_count = validate_ohlcv_series(raw_bars, now_ms=now)
        self._metrics.invalid_count += invalid_count
        if not valid:
            self._metrics.request_failures += 1
            raise MarketDataError(
                f"no valid OHLCV bars for {ns.symbol} {timeframe}",
                exchange_id=self.exchange_id,
            )

        missing, gap_report = detect_gaps(valid, timeframe)
        self._metrics.missing_candles = len(missing)
        self._metrics.duplicate_count += gap_report.duplicate_count

        bars_tuple = tuple(valid)
        merged = self._cache.merge_ohlcv(
            self.exchange_id, ns.symbol, timeframe, bars_tuple, now_ms=now
        )
        quality = self._ohlcv_freshness(merged, timeframe, gap_report, now)
        self._metrics.last_ohlcv_update_ms = now
        self._metrics.ohlcv_age_ms = now - merged[-1].timestamp_ms if merged else None

        return OHLCVSnapshot(
            bars=merged,
            symbol=ns,
            timeframe=timeframe,
            quality=quality,
            fetched_at_ms=now,
        )

    def _ohlcv_freshness(
        self,
        bars: Sequence[OHLCVBar],
        timeframe: str,
        gap_report: DataQualityReport,
        now_ms: int,
    ) -> DataQualityReport:
        if not bars:
            return DataQualityReport(quality=DataQuality.UNKNOWN, reasons=("empty",))
        interval = timeframe_to_ms(timeframe)
        max_age = interval * self._config.ohlcv_stale_bars
        last_ts = bars[-1].timestamp_ms
        if is_stale(last_ts, max_age, now_ms=now_ms):
            return DataQualityReport(
                quality=DataQuality.STALE,
                reasons=("last bar stale", *gap_report.reasons),
                missing_timestamps_ms=gap_report.missing_timestamps_ms,
                duplicate_count=gap_report.duplicate_count,
            )
        return gap_report

    # ------------------------------------------------------------------
    # Order book
    # ------------------------------------------------------------------

    def get_order_book(
        self,
        symbol: str,
        *,
        limit: int | None = None,
        use_cache: bool = True,
        force_refresh: bool = False,
    ) -> OrderBookSnapshot:
        now = utc_now_ms()
        ns = self.resolve_symbol(symbol)
        native = self._native_for(symbol)

        if use_cache and not force_refresh:
            cached = self._cache.get_orderbook(self.exchange_id, ns.symbol, now_ms=now)
            if cached is not None:
                self._metrics.cache_hits += 1
                quality = self._orderbook_quality(cached, now)
                return OrderBookSnapshot(book=cached, symbol=ns, quality=quality, fetched_at_ms=now)
            self._metrics.cache_misses += 1

        self._throttle("orderbook")
        try:
            book = self._adapter.fetch_order_book(native, limit=limit)
        except RateLimitError:
            self._metrics.rate_limit_events += 1
            self._metrics.request_failures += 1
            raise
        except ExchangeError:
            self._metrics.request_failures += 1
            raise

        quality = self._orderbook_quality(book, now)
        if quality.quality is DataQuality.INVALID:
            self._metrics.invalid_count += 1
            raise MarketDataError(
                f"invalid order book for {ns.symbol}: {quality.reasons}",
                exchange_id=self.exchange_id,
            )

        self._cache.put_orderbook(self.exchange_id, ns.symbol, book, now_ms=now)
        self._metrics.last_orderbook_update_ms = now
        self._metrics.orderbook_age_ms = (
            now - book.timestamp_ms if book.timestamp_ms is not None else 0
        )
        return OrderBookSnapshot(book=book, symbol=ns, quality=quality, fetched_at_ms=now)

    def _orderbook_quality(self, book: OrderBook, now_ms: int) -> DataQualityReport:
        if not book.bids and not book.asks:
            return DataQualityReport(quality=DataQuality.PARTIAL, reasons=("empty order book",))
        if book.bids and book.asks and book.bids[0].price >= book.asks[0].price:
            return DataQualityReport(quality=DataQuality.INVALID, reasons=("crossed book",))
        if is_stale(
            book.timestamp_ms,
            self._config.orderbook_stale_ms,
            now_ms=now_ms,
        ):
            return DataQualityReport(quality=DataQuality.STALE, reasons=("stale order book",))
        return DataQualityReport(quality=DataQuality.COMPLETE)

    # ------------------------------------------------------------------
    # Pass-through read helpers (still read-only)
    # ------------------------------------------------------------------

    def get_balance(self) -> Sequence[AssetBalance]:
        return self._adapter.fetch_balance()

    # ------------------------------------------------------------------
    # Cache / metrics
    # ------------------------------------------------------------------

    def cache_stats(self) -> dict[str, int]:
        return self._cache.stats

    def clear_cache(self) -> None:
        self._cache.clear()

    def metrics_snapshot(self) -> dict[str, object]:
        snap = self._metrics.snapshot()
        snap["cache"] = self.cache_stats()
        snap["health"] = self.health().name
        return snap

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _throttle(self, key: str) -> None:
        """Simple per-key minimum interval to avoid hammering the exchange."""
        now = utc_now_ms()
        last = self._last_poll_ms.get(key)
        if last is not None:
            elapsed = now - last
            min_i = self._config.min_poll_interval_ms
            if elapsed < min_i:
                time.sleep((min_i - elapsed) / 1000.0)
        self._last_poll_ms[key] = utc_now_ms()
