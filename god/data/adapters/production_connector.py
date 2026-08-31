"""Phase 6B — N.U.N.G. production market data connector.

Wires Phase 6A ProductionConfig to existing ProductionMarketDataSource.
READ market data only. No trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from god.data.adapters.production import (
    FakeProviderTransport,
    ProductionMarketDataSource,
    ProviderTransport,
)
from god.data.circuit import CircuitBreaker, CircuitBreakerConfig
from god.data.health import SourceHealth, SourceHealthState
from god.data.models import MarketBar, MarketDataSnapshot
from god.data.retry import RetryPolicy
from god.production.config import ExecutionMode, ProductionConfig
from god.production.validation import ConfigValidationStatus, validate_config


@dataclass(frozen=True)
class ConnectorConfig:
    """Safe connector settings derived from ProductionConfig (no secrets)."""

    provider_name: str
    data_source_id: str
    max_symbols: int
    max_bars: int
    max_retries: int
    timeout_seconds: float
    environment: str
    execution_mode: str

    @classmethod
    def from_production_config(cls, cfg: ProductionConfig) -> "ConnectorConfig":
        # timeout/retry from extra if present, else defaults
        extra = cfg.extra or {}
        timeout = float(extra.get("data_timeout_seconds", 5.0))
        retries = int(extra.get("data_max_retries", 2))
        if timeout <= 0 or timeout > 300:
            timeout = 5.0
        if retries < 0 or retries > 10:
            retries = 2
        return cls(
            provider_name=str(extra.get("provider_name", cfg.data_source_id)),
            data_source_id=cfg.data_source_id,
            max_symbols=cfg.resource_limits.max_symbols,
            max_bars=cfg.resource_limits.max_bars,
            max_retries=retries,
            timeout_seconds=timeout,
            environment=cfg.environment.value,
            execution_mode=cfg.execution_mode.value,
        )


class ProductionMarketDataConnector:
    """
    Production-grade boundary:
      ProductionConfig → ConnectorConfig → ProductionMarketDataSource

    Does NOT submit orders. Does NOT open positions.
    LIVE execution mode on config → connector refuses to start (fail-closed).
    """

    def __init__(
        self,
        production_config: ProductionConfig,
        transport: Optional[ProviderTransport] = None,
        *,
        now_fn=None,
    ) -> None:
        validation = validate_config(production_config)
        if validation.status == ConfigValidationStatus.BLOCKED:
            raise ValueError(f"config_blocked:{','.join(validation.reasons)}")
        if validation.status != ConfigValidationStatus.VALID:
            raise ValueError(f"config_invalid:{','.join(validation.reasons)}")
        if production_config.execution_mode == ExecutionMode.LIVE:
            raise ValueError("live_execution_not_authorized_for_data_connector")
        if production_config.feature_flags.live_execution:
            raise ValueError("live_feature_flag_blocked")

        self.production_config = production_config
        self.connector_config = ConnectorConfig.from_production_config(production_config)
        self.transport = transport or FakeProviderTransport()
        policy = RetryPolicy(max_retries=self.connector_config.max_retries)
        circuit = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=3, cooldown_seconds=30.0),
            now_fn=now_fn or (lambda: 0.0),
        )
        self.source = ProductionMarketDataSource(
            self.transport,
            source_id=f"prod:{self.connector_config.provider_name}",
            max_retries=self.connector_config.max_retries,
            retry_policy=policy,
            circuit=circuit,
            now_fn=now_fn,
        )

    def fetch_universe(self) -> list[str]:
        uni = self.source.fetch_universe()
        return uni[: self.connector_config.max_symbols]

    def fetch_bars(self, symbol: str, *, max_bars: Optional[int] = None) -> list[MarketBar]:
        limit = max_bars if max_bars is not None else self.connector_config.max_bars
        limit = min(limit, self.connector_config.max_bars)
        return self.source.fetch_bars(symbol, max_bars=limit)

    def source_health(self) -> SourceHealth:
        return self.source.source_health()

    def as_market_data_source(self) -> ProductionMarketDataSource:
        """Expose underlying source for MarketDataIngestion / run_cycle_from_source."""
        return self.source

    def telemetry(self) -> dict[str, Any]:
        base = self.source.telemetry() if hasattr(self.source, "telemetry") else {}
        return {
            **base,
            "provider_name": self.connector_config.provider_name,
            "data_source_id": self.connector_config.data_source_id,
            "environment": self.connector_config.environment,
            "execution_mode": self.connector_config.execution_mode,
            "max_symbols": self.connector_config.max_symbols,
            "max_bars": self.connector_config.max_bars,
            # never include secrets
        }
