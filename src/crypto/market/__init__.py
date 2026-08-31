"""Market Data Engine (Phase 3 — read-only).

Provides validated, normalized, cached market data on top of ExchangeAdapter.
No order execution. No trading decisions.
"""

from crypto.market.config import DEFAULT_TIMEFRAMES, MarketDataConfig
from crypto.market.engine import (
    MarketDataEngine,
    OHLCVSnapshot,
    OrderBookSnapshot,
    TickerSnapshot,
)
from crypto.market.quality import DataQuality, DataQualityReport, MarketDataMetrics
from crypto.market.symbols import NormalizedSymbol, normalize_symbol

__all__ = [
    "MarketDataEngine",
    "MarketDataConfig",
    "DEFAULT_TIMEFRAMES",
    "TickerSnapshot",
    "OHLCVSnapshot",
    "OrderBookSnapshot",
    "DataQuality",
    "DataQualityReport",
    "MarketDataMetrics",
    "NormalizedSymbol",
    "normalize_symbol",
]
