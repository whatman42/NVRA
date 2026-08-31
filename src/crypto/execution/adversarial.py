"""Adversarial paper broker — non-frictionless simulation profiles."""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass
from typing import Any

from crypto.market.timeutils import utc_now_ms
from ._order_utils import cancel_order_state


@dataclass(frozen=True, slots=True)
class AdversarialSimulationProfile:
    """All knobs explicit — no hidden 'make paper look good' defaults."""

    name: str = "default"
    latency_ms: float = 50.0
    spread_bps: float = 10.0  # half-spread applied against taker
    slippage_bps: float = 5.0
    partial_fill_ratio: float = 1.0  # 1.0 = full fill
    reject_probability: float = 0.0
    timeout_probability: float = 0.0
    insufficient_liquidity_probability: float = 0.0
    fee_pct: float = 0.1
    min_notional: float = 0.0
    tick_size: float = 0.0
    step_size: float = 0.0
    max_order_book_depth: float = 1e12  # liquidity cap in base units
    seed: int | None = 42


# Preset profiles for chaos / acceptance
PROFILES: dict[str, AdversarialSimulationProfile] = {
    "ideal": AdversarialSimulationProfile(name="ideal", latency_ms=0, spread_bps=0, slippage_bps=0),
    "retail": AdversarialSimulationProfile(
        name="retail", latency_ms=120, spread_bps=15, slippage_bps=8, fee_pct=0.15
    ),
    "hostile": AdversarialSimulationProfile(
        name="hostile",
        latency_ms=800,
        spread_bps=40,
        slippage_bps=25,
        partial_fill_ratio=0.4,
        reject_probability=0.15,
        timeout_probability=0.05,
        insufficient_liquidity_probability=0.1,
        fee_pct=0.2,
        max_order_book_depth=0.5,
    ),
    "micro": AdversarialSimulationProfile(
        name="micro",
        latency_ms=200,
        spread_bps=30,
        slippage_bps=15,
        fee_pct=0.2,
        min_notional=10.0,
        tick_size=0.01,
        step_size=0.0001,
    ),
}


class AdversarialPaperBroker:
    """Paper broker with latency, spread, slippage, rejects, partials, timeouts."""

    def __init__(self, profile: AdversarialSimulationProfile | None = None) -> None:
        self.profile = profile or PROFILES["retail"]
        self._rng = random.Random(self.profile.seed)
        self._orders: dict[str, dict[str, Any]] = {}
        self._id = itertools.count(1)
        self.simulated_latency_ms = self.profile.latency_ms

    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None = None,
        client_order_id: str | None = None,
        *,
        mid_price: float | None = None,
    ) -> dict[str, Any]:
        p = self.profile
        mid = (
            mid_price
            if mid_price is not None and mid_price > 0
            else (price if price is not None and price > 0 else 1.0)
        )

        # Precision / min notional
        if p.step_size > 0:
            steps = int(amount / p.step_size)
            amount = steps * p.step_size
        if amount <= 0:
            return self._reject(
                symbol, side, order_type, amount, price, client_order_id, "step_size"
            )

        # Timeout / reject / liquidity
        if self._rng.random() < p.timeout_probability:
            return {
                "id": None,
                "clientOrderId": client_order_id,
                "status": "unknown",
                "error": "timeout",
                "timestamp": utc_now_ms(),
            }
        if self._rng.random() < p.reject_probability:
            return self._reject(
                symbol, side, order_type, amount, price, client_order_id, "rejected"
            )
        if self._rng.random() < p.insufficient_liquidity_probability:
            return self._reject(
                symbol, side, order_type, amount, price, client_order_id, "insufficient_liquidity"
            )

        # Apply spread + slippage against taker
        half = mid * (p.spread_bps / 10_000.0)
        slip = mid * (p.slippage_bps / 10_000.0)
        px = mid + half + slip if side.lower() == "buy" else mid - half - slip
        if p.tick_size > 0:
            px = round(px / p.tick_size) * p.tick_size

        notional = amount * px
        if p.min_notional > 0 and notional < p.min_notional:
            return self._reject(
                symbol, side, order_type, amount, px, client_order_id, "min_notional"
            )

        # Liquidity cap → partial
        fill_cap = min(amount, p.max_order_book_depth)
        filled = min(fill_cap, amount * max(0.0, min(1.0, p.partial_fill_ratio)))
        remaining = max(0.0, amount - filled)
        if filled <= 0:
            return self._reject(
                symbol, side, order_type, amount, px, client_order_id, "no_liquidity"
            )

        status = "closed" if remaining <= 1e-12 else "open"
        fee = filled * px * (p.fee_pct / 100.0)
        oid = f"adv-paper-{next(self._id)}"
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
            "average": px,
            "timestamp": utc_now_ms(),
            "fee": {"cost": fee, "currency": None},
            "latency_ms": p.latency_ms,
            "mode": "PAPER",
        }
        self._orders[oid] = order
        return dict(order)

    def _reject(
        self,
        symbol: str,
        side: str,
        order_type: str,
        amount: float,
        price: float | None,
        client_order_id: str | None,
        reason: str,
    ) -> dict[str, Any]:
        oid = f"adv-paper-{next(self._id)}"
        order = {
            "id": oid,
            "clientOrderId": client_order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "status": "rejected",
            "price": price,
            "amount": amount,
            "filled": 0.0,
            "remaining": amount,
            "average": None,
            "timestamp": utc_now_ms(),
            "fee": {"cost": 0.0, "currency": None},
            "error": reason,
            "mode": "PAPER",
        }
        self._orders[oid] = order
        return dict(order)

    def fetch_order(self, order_id: str, symbol: str | None = None) -> dict[str, Any] | None:
        o = self._orders.get(order_id)
        return dict(o) if o else None

    def cancel_order(self, order_id: str, symbol: str | None = None) -> dict[str, Any]:
        return cancel_order_state(self._orders, order_id)
