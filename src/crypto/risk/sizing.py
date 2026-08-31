"""Deterministic position sizing.

Never rounds up through risk limits to meet exchange minimums.
"""

from __future__ import annotations

from dataclasses import dataclass

from crypto.risk.models import MarketConstraints
from crypto.risk.policy import RiskPolicy


@dataclass(frozen=True, slots=True)
class SizingResult:
    max_quantity: float
    max_notional: float
    fee_estimate: float
    slippage_estimate: float
    limited_by: str  # human-readable binding constraint


def _floor_precision(value: float, precision: int | None) -> float:
    if precision is None or precision < 0:
        return value
    factor = 10**precision
    return float(int(value * factor)) / float(factor)


def compute_position_size(
    *,
    equity: float,
    available_balance: float,
    entry_price: float,
    policy: RiskPolicy,
    constraints: MarketConstraints | None = None,
    stop_price: float | None = None,
    existing_symbol_exposure: float = 0.0,
    existing_exchange_exposure: float = 0.0,
    existing_portfolio_exposure: float = 0.0,
) -> SizingResult:
    """Compute maximum allowed quantity / notional for a new long-style entry.

    Binding constraints (all applied; the tightest wins):
      1. risk_per_trade_pct with stop distance (if stop provided)
      2. max_position_pct of equity
      3. remaining room under symbol / exchange / portfolio exposure caps
      4. available balance after fee + slippage reserve
      5. exchange min_amount / min_cost (reject path handled by caller if result below min)
    """
    if equity <= 0 or available_balance <= 0 or entry_price <= 0:
        return SizingResult(0.0, 0.0, 0.0, 0.0, "zero_equity_or_price")

    constraints = constraints or MarketConstraints()
    fee_pct = (
        constraints.taker_fee_pct
        if constraints.taker_fee_pct is not None
        else policy.default_taker_fee_pct
    )
    slip_pct = policy.default_slippage_pct
    cost_factor = 1.0 + (fee_pct + slip_pct) / 100.0

    candidates: list[tuple[float, str]] = []  # (max_notional, reason)

    # 1. Stop-based risk budget
    if stop_price is not None and stop_price > 0 and stop_price < entry_price:
        stop_dist = entry_price - stop_price
        risk_budget = equity * (policy.risk_per_trade_pct / 100.0)
        if stop_dist > 0:
            qty = risk_budget / stop_dist
            candidates.append((qty * entry_price, "stop_risk"))

    # 2. Max position % of equity
    candidates.append((equity * (policy.max_position_pct / 100.0), "max_position_pct"))

    # 3. Exposure headroom
    def _headroom(cap_pct: float, existing: float) -> float:
        cap = equity * (cap_pct / 100.0)
        return max(0.0, cap - existing)

    candidates.append(
        (
            _headroom(policy.max_symbol_exposure_pct, existing_symbol_exposure),
            "max_symbol_exposure",
        )
    )
    candidates.append(
        (
            _headroom(policy.max_exchange_exposure_pct, existing_exchange_exposure),
            "max_exchange_exposure",
        )
    )
    candidates.append(
        (
            _headroom(policy.max_portfolio_exposure_pct, existing_portfolio_exposure),
            "max_portfolio_exposure",
        )
    )

    # 4. Available balance (reserve fees + slippage)
    spendable = available_balance / cost_factor
    candidates.append((spendable, "available_balance"))

    if policy.min_notional > 0:
        # Not a cap — applied later as floor check by risk engine
        pass

    # Tightest notional
    max_notional, limited_by = min(candidates, key=lambda x: x[0])
    if max_notional <= 0:
        return SizingResult(0.0, 0.0, 0.0, 0.0, limited_by)

    max_qty = max_notional / entry_price
    max_qty = _floor_precision(max_qty, constraints.amount_precision)
    max_notional = max_qty * entry_price

    fee_est = max_notional * (fee_pct / 100.0)
    slip_est = max_notional * (slip_pct / 100.0)

    return SizingResult(
        max_quantity=max(0.0, max_qty),
        max_notional=max(0.0, max_notional),
        fee_estimate=fee_est,
        slippage_estimate=slip_est,
        limited_by=limited_by,
    )


def meets_exchange_minimums(
    quantity: float,
    price: float,
    constraints: MarketConstraints | None,
) -> bool:
    """True if quantity/notional satisfy exchange minimums."""
    if quantity <= 0 or price <= 0:
        return False
    if constraints is None:
        return True
    if constraints.min_amount is not None and quantity < constraints.min_amount:
        return False
    notional = quantity * price
    return not (constraints.min_cost is not None and notional < constraints.min_cost)
