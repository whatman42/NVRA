"""Normalized domain models for exchange data.

These types are independent of CCXT. Adapters translate exchange-specific
responses into these models before data leaves the exchanges package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class ConnectionHealth(Enum):
    """Lightweight connection health states."""

    DISCONNECTED = auto()
    CONNECTING = auto()
    CONNECTED = auto()
    DEGRADED = auto()
    AUTH_FAILED = auto()
    RATE_LIMITED = auto()
    EXCHANGE_UNAVAILABLE = auto()
    UNKNOWN = auto()


class PermissionStatus(Enum):
    """Whether a capability is available for the current API key."""

    GRANTED = auto()
    DENIED = auto()
    UNKNOWN = auto()


class MarketType(Enum):
    SPOT = auto()
    MARGIN = auto()
    SWAP = auto()
    FUTURE = auto()
    OPTION = auto()
    UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class PermissionReport:
    """Read-only view of what the current API key can do.

    Trading and withdrawal are reported when the exchange exposes the
    information; otherwise UNKNOWN. No trades are executed to probe.
    """

    authenticated: bool
    market_data: PermissionStatus
    account_read: PermissionStatus
    trading: PermissionStatus
    withdrawal: PermissionStatus
    warnings: tuple[str, ...] = ()

    @property
    def has_withdrawal_warning(self) -> bool:
        return self.withdrawal is PermissionStatus.GRANTED


@dataclass(frozen=True, slots=True)
class Market:
    """Normalized market metadata."""

    exchange: str
    symbol: str
    base_asset: str
    quote_asset: str
    active: bool | None
    market_type: MarketType
    price_precision: int | None
    amount_precision: int | None
    minimum_amount: float | None
    minimum_cost: float | None
    maker_fee: float | None
    taker_fee: float | None


@dataclass(frozen=True, slots=True)
class AssetBalance:
    """Normalized balance for a single asset.

    free + used is NOT assumed to equal total unless the exchange
    response has been validated to guarantee that relationship.
    """

    asset: str
    free: float | None
    used: float | None
    total: float | None


@dataclass(frozen=True, slots=True)
class Ticker:
    """Normalized ticker snapshot."""

    exchange: str
    symbol: str
    timestamp_ms: int | None
    bid: float | None
    ask: float | None
    last: float | None
    high: float | None
    low: float | None
    volume: float | None
    quote_volume: float | None


@dataclass(frozen=True, slots=True)
class OHLCVBar:
    """Single OHLCV candle."""

    timestamp_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    price: float
    amount: float


@dataclass(frozen=True, slots=True)
class OrderBook:
    """Normalized order book snapshot."""

    exchange: str
    symbol: str
    timestamp_ms: int | None
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]


@dataclass(frozen=True, slots=True)
class OpenOrder:
    """Normalized open order (read-only view)."""

    exchange: str
    id: str
    client_order_id: str | None
    symbol: str
    side: str
    order_type: str
    status: str
    price: float | None
    amount: float | None
    filled: float | None
    remaining: float | None
    timestamp_ms: int | None


@dataclass(frozen=True, slots=True)
class Trade:
    """Normalized user trade (read-only)."""

    exchange: str
    id: str
    order_id: str | None
    symbol: str
    side: str
    price: float
    amount: float
    cost: float | None
    fee_cost: float | None
    fee_currency: str | None
    timestamp_ms: int | None


@dataclass(frozen=True, slots=True)
class Position:
    """Normalized position (for derivatives; often empty on spot)."""

    exchange: str
    symbol: str
    side: str | None
    size: float | None
    entry_price: float | None
    unrealized_pnl: float | None
    leverage: float | None
    raw: dict[str, Any] = field(default_factory=dict, compare=False)
