"""Data quality states and lightweight metrics for market data."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any


class DataQuality(Enum):
    """Explicit quality of a market-data snapshot or series."""

    COMPLETE = auto()
    PARTIAL = auto()
    GAP_DETECTED = auto()
    STALE = auto()
    INVALID = auto()
    UNKNOWN = auto()


@dataclass(slots=True)
class DataQualityReport:
    """Quality assessment attached to engine responses."""

    quality: DataQuality
    reasons: tuple[str, ...] = ()
    missing_timestamps_ms: tuple[int, ...] = ()
    duplicate_count: int = 0
    invalid_count: int = 0

    @property
    def is_usable(self) -> bool:
        return self.quality in (
            DataQuality.COMPLETE,
            DataQuality.PARTIAL,
            DataQuality.GAP_DETECTED,
        )


@dataclass(slots=True)
class MarketDataMetrics:
    """Lightweight runtime metrics (not a full observability stack)."""

    last_ticker_update_ms: int | None = None
    last_ohlcv_update_ms: int | None = None
    last_orderbook_update_ms: int | None = None
    ticker_age_ms: int | None = None
    ohlcv_age_ms: int | None = None
    orderbook_age_ms: int | None = None
    missing_candles: int = 0
    duplicate_count: int = 0
    invalid_count: int = 0
    request_failures: int = 0
    rate_limit_events: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "last_ticker_update_ms": self.last_ticker_update_ms,
            "last_ohlcv_update_ms": self.last_ohlcv_update_ms,
            "last_orderbook_update_ms": self.last_orderbook_update_ms,
            "ticker_age_ms": self.ticker_age_ms,
            "ohlcv_age_ms": self.ohlcv_age_ms,
            "orderbook_age_ms": self.orderbook_age_ms,
            "missing_candles": self.missing_candles,
            "duplicate_count": self.duplicate_count,
            "invalid_count": self.invalid_count,
            "request_failures": self.request_failures,
            "rate_limit_events": self.rate_limit_events,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }
