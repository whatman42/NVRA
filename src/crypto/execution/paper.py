"""Paper trading simulator — same state machine path, never hits real exchange."""

from __future__ import annotations

import itertools
from typing import Any

from crypto.market.timeutils import utc_now_ms
from ._order_utils import cancel_order_state

_id_counter = itertools.count(1)


class PaperBroker:
    """In-process fill simulator for PAPER mode."""

    def __init__(self, *, fill_ratio: float = 1.0, default_fee_pct: float = 0.1) -> None:
        self._fill_ratio = max(0.0, min(1.0, fill_ratio))
        self._fee_pct = default_fee_pct
        self._orders: dict[str, dict[str, Any]] = {}

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        client_order_id: str | None = None,
    ) -> dict[str, Any]:
        oid = f"paper-{next(_id_counter)}"
        px = price if price is not None and price > 0 else 1.0
        filled = amount * self._fill_ratio
        remaining = amount - filled
        status = "closed" if remaining <= 1e-12 else ("open" if filled <= 0 else "open")
        if filled > 0 and remaining > 1e-12:
            status = "open"  # partial
        fee = filled * px * (self._fee_pct / 100.0)
        order = {
            "id": oid,
            "clientOrderId": client_order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "status": status,
            "price": px,
            "amount": amount,
            "filled": filled,
            "remaining": remaining,
            "average": px if filled > 0 else None,
            "timestamp": utc_now_ms(),
            "fee": {"cost": fee, "currency": None},
        }
        self._orders[oid] = order
        return dict(order)

    def cancel_order(self, order_id: str, symbol: str | None = None) -> dict[str, Any]:
        return cancel_order_state(self._orders, order_id)

    def fetch_order(self, order_id: str, symbol: str | None = None) -> dict[str, Any] | None:
        return dict(self._orders[order_id]) if order_id in self._orders else None
