"""Configuration for the Market Data Engine.

Bounds exist so a future hardware governor (Phase 9) can tighten limits
without redesigning the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

# Supported timeframes (minimum set required by Phase 3).
DEFAULT_TIMEFRAMES: tuple[str, ...] = ("1m", "5m", "15m", "1h", "4h")


@dataclass(frozen=True, slots=True)
class MarketDataConfig:
    """Bounded, low-resource market-data configuration."""

    # Subscriptions — empty means "no automatic polling; on-demand only"
    symbols: tuple[str, ...] = ()
    timeframes: tuple[str, ...] = DEFAULT_TIMEFRAMES

    # Freshness thresholds (milliseconds)
    ticker_stale_ms: int = 30_000  # 30s
    orderbook_stale_ms: int = 15_000  # 15s
    # OHLCV staleness scales with timeframe; this is a multiplier on bar size
    ohlcv_stale_bars: int = 3  # stale after N missing bar intervals

    # Cache bounds (critical for low-RAM hardware)
    max_symbols: int = 20
    max_candles_per_key: int = 500  # per (exchange, symbol, timeframe)
    max_ticker_entries: int = 50
    max_orderbook_entries: int = 30
    cache_ttl_ms: int = 300_000  # 5 minutes generic TTL

    # Polling / rate awareness
    min_poll_interval_ms: int = 1_000
    default_ohlcv_limit: int = 100

    # Future-timestamp tolerance
    future_tolerance_ms: int = 60_000

    def validate(self) -> None:
        if self.max_symbols < 1:
            raise ValueError("max_symbols must be >= 1")
        if self.max_candles_per_key < 1:
            raise ValueError("max_candles_per_key must be >= 1")
        if self.ticker_stale_ms < 0 or self.orderbook_stale_ms < 0:
            raise ValueError("stale thresholds must be >= 0")
        if self.ohlcv_stale_bars < 1:
            raise ValueError("ohlcv_stale_bars must be >= 1")
        for tf in self.timeframes:
            if not tf or not isinstance(tf, str):
                raise ValueError(f"invalid timeframe: {tf!r}")
