"""Shared deterministic paper-order state transitions."""
from __future__ import annotations
from typing import Any


def cancel_order_state(orders: dict[str, dict[str, Any]], order_id: str) -> dict[str, Any]:
    order = orders.get(order_id)
    if order is None:
        return {"id": order_id, "status": "canceled"}
    updated = dict(order)
    updated["status"] = "canceled"
    updated["remaining"] = 0.0
    orders[order_id] = updated
    return updated
