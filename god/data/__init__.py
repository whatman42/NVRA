"""Phase 4L — Autonomous market data ingestion & normalization.

No MT5, no broker, no execution. Cognitive data path only.
"""

from .models import (
    DataQualityState,
    IngestionStatus,
    MarketBar,
    MarketDataSnapshot,
    SymbolSeries,
)
from .source import MarketDataSource
from .ingestion import MarketDataIngestion
from .adapters import InMemoryMarketDataSource, ProductionMarketDataSource, FakeProviderTransport, ProductionMarketDataConnector, ConnectorConfig
from .health import SourceHealth, SourceHealthState
from .integrity import integrity_check_series, validate_ohlc_bar
from .retry import RetryPolicy, FailureClass, run_with_retry, classify_exception
from .circuit import CircuitBreaker, CircuitState, CircuitBreakerConfig
from .rate_limit import RateLimitGuard, RateLimitInfo
from .single_flight import SingleFlight
from .bridge import run_cycle_from_source, snapshot_to_loop_kwargs
from .validation import validate_series
from .normalization import normalize_bar, normalize_series

__all__ = [
    "DataQualityState",
    "IngestionStatus",
    "MarketBar",
    "MarketDataSnapshot",
    "SymbolSeries",
    "MarketDataSource",
    "MarketDataIngestion",
    "InMemoryMarketDataSource",
    "ProductionMarketDataSource",
    "FakeProviderTransport",
    "ProductionMarketDataConnector",
    "ConnectorConfig",
    "SourceHealth",
    "SourceHealthState",
    "integrity_check_series",
    "validate_ohlc_bar",
    "RetryPolicy",
    "FailureClass",
    "run_with_retry",
    "classify_exception",
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerConfig",
    "RateLimitGuard",
    "RateLimitInfo",
    "SingleFlight",

    "run_cycle_from_source",
    "snapshot_to_loop_kwargs",
    "validate_series",
    "normalize_bar",
    "normalize_series",
]
