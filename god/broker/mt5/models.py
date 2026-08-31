"""DTOs for MT5 adapter — no trading decisions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class MT5AccountMode(str, Enum):
    UNKNOWN = "UNKNOWN"
    DEMO = "DEMO"
    CONTEST = "CONTEST"
    LIVE = "LIVE"


class OrderRequestType(str, Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


@dataclass(frozen=True)
class MT5Tick:
    symbol: str
    bid: float
    ask: float
    time: int
    volume: float = 0.0

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)


@dataclass
class MT5OrderRequest:
    client_order_id: str
    symbol: str
    side: str  # BUY | SELL
    volume: float
    order_type: OrderRequestType = OrderRequestType.MARKET
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: str = "NVRA"

    def to_audit(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "order_type": self.order_type.value,
            "sl": self.sl,
            "tp": self.tp,
            "comment": self.comment,
        }


@dataclass
class MT5OrderResult:
    ok: bool
    status: str  # ACCEPTED | REJECTED | FILLED | PARTIAL | UNKNOWN
    broker_order_id: Optional[str] = None
    deal_id: Optional[str] = None
    filled_volume: float = 0.0
    price: Optional[float] = None
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "broker_order_id": self.broker_order_id,
            "deal_id": self.deal_id,
            "filled_volume": self.filled_volume,
            "price": self.price,
            "message": self.message,
        }
