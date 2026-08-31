"""Opportunity model with mandatory reason codes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from crypto.ensemble.aggregate import EnsemblePrediction
from crypto.market.quality import DataQuality
from crypto.portfolio.models import AccountKey


class ReasonCode(Enum):
    BALANCE_AVAILABLE = auto()
    INSUFFICIENT_BALANCE = auto()
    LOW_LIQUIDITY = auto()
    HIGH_SPREAD = auto()
    STALE_DATA = auto()
    INVALID_DATA = auto()
    HIGH_DISAGREEMENT = auto()
    MIN_ORDER_UNFEASIBLE = auto()
    STRONG_SIGNAL = auto()
    HIGH_VOLATILITY = auto()
    RISK_BLOCKED = auto()
    MARKET_INACTIVE = auto()
    NOT_REACHABLE = auto()
    FEE_EXCEEDS_EDGE = auto()
    DUPLICATE_EXPOSURE = auto()
    PASSED_FILTERS = auto()
    RANKED = auto()


class Feasibility(Enum):
    FEASIBLE = auto()
    ORDER_NOT_FEASIBLE = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class Opportunity:
    exchange_id: str
    account_id: str
    symbol: str
    base_asset: str
    quote_asset: str
    native_symbol: str
    available_quote: float
    available_base: float
    market_quality: DataQuality
    spread_pct: float | None
    liquidity_score: float  # 0..1
    volatility: float
    ensemble: EnsemblePrediction | None
    opportunity_score: float
    feasibility: Feasibility
    reason_codes: tuple[ReasonCode, ...]
    mid_price: float | None = None
    min_cost: float | None = None
    estimated_fee_pct: float = 0.1

    @property
    def account(self) -> AccountKey:
        return AccountKey(self.exchange_id, self.account_id)


@dataclass(slots=True)
class ScanTelemetry:
    markets_scanned: int = 0
    asset_filtered: int = 0
    liquidity_filtered: int = 0
    spread_filtered: int = 0
    quality_rejected: int = 0
    ml_candidates: int = 0
    predictions: int = 0
    final_opportunities: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

    def snapshot(self) -> dict[str, int]:
        return {
            "markets_scanned": self.markets_scanned,
            "asset_filtered": self.asset_filtered,
            "liquidity_filtered": self.liquidity_filtered,
            "spread_filtered": self.spread_filtered,
            "quality_rejected": self.quality_rejected,
            "ml_candidates": self.ml_candidates,
            "predictions": self.predictions,
            "final_opportunities": self.final_opportunities,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }
