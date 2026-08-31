"""Normalized portfolio and position models.

Exchange state is the source of truth. Local portfolio is a reconstruction
layer used for risk, PnL, and reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class PositionSide(Enum):
    LONG = auto()
    SHORT = auto()
    FLAT = auto()


@dataclass(frozen=True, slots=True)
class AccountKey:
    """Identifies an exchange account. Never aggregates across exchanges."""

    exchange_id: str
    account_id: str = "default"

    def __str__(self) -> str:
        return f"{self.exchange_id}/{self.account_id}"


@dataclass(frozen=True, slots=True)
class AssetHolding:
    """Balance for a single asset on a single exchange account."""

    account: AccountKey
    asset: str
    free: float
    used: float
    total: float


@dataclass(frozen=True, slots=True)
class Position:
    """Normalized position on one symbol / one exchange account."""

    account: AccountKey
    symbol: str
    side: PositionSide
    quantity: float
    average_entry: float | None
    current_price: float | None
    market_value: float | None
    unrealized_pnl: float | None
    realized_pnl: float
    fees: float
    opened_at_ms: int | None
    updated_at_ms: int | None

    def __post_init__(self) -> None:
        if self.quantity < 0:
            raise ValueError("position quantity must be >= 0")
        if self.side is PositionSide.FLAT and self.quantity != 0:
            raise ValueError("FLAT position must have quantity 0")
        if self.side is not PositionSide.FLAT and self.quantity == 0:
            raise ValueError("non-FLAT position must have quantity > 0")


@dataclass(frozen=True, slots=True)
class ExposureBreakdown:
    """Exposure metrics. No double counting across dimensions."""

    gross: float
    net: float
    by_symbol: dict[str, float] = field(default_factory=dict)
    by_exchange: dict[str, float] = field(default_factory=dict)
    by_asset: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Point-in-time portfolio state (possibly multi-exchange)."""

    equity: float
    available_balance: float
    reserved_balance: float
    holdings: tuple[AssetHolding, ...]
    positions: tuple[Position, ...]
    unrealized_pnl: float
    realized_pnl: float
    fees: float
    exposure: ExposureBreakdown
    timestamp_ms: int
    quote_currency: str = "USDT"
    accounts: tuple[AccountKey, ...] = ()

    def positions_for(self, account: AccountKey) -> tuple[Position, ...]:
        return tuple(p for p in self.positions if p.account == account)

    def holdings_for(self, account: AccountKey) -> tuple[AssetHolding, ...]:
        return tuple(h for h in self.holdings if h.account == account)

    def open_position_count(self) -> int:
        return sum(1 for p in self.positions if p.side is not PositionSide.FLAT)


@dataclass(frozen=True, slots=True)
class ReconciliationIssue:
    """A single detected discrepancy between local and exchange state."""

    kind: str  # balance_mismatch | position_mismatch | unknown_trade | unknown_order | stale
    account: AccountKey
    detail: str
    local_value: float | str | None = None
    exchange_value: float | str | None = None


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Typed result of comparing local portfolio vs exchange state."""

    matched: bool
    issues: tuple[ReconciliationIssue, ...]
    checked_at_ms: int

    @property
    def has_mismatch(self) -> bool:
        return not self.matched
