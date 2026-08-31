"""Cheap pre-ML filters."""

from __future__ import annotations

from crypto.market.quality import DataQuality
from crypto.scanner.config import ScannerConfig
from crypto.scanner.opportunity import Feasibility, ReasonCode
from crypto.scanner.universe import ReachableMarket


def filter_spread(spread_pct: float | None, config: ScannerConfig) -> tuple[bool, list[ReasonCode]]:
    if spread_pct is None:
        return True, []
    if spread_pct > config.max_spread_pct:
        return False, [ReasonCode.HIGH_SPREAD]
    return True, []


def filter_quality(quality: DataQuality) -> tuple[bool, list[ReasonCode]]:
    if quality is DataQuality.STALE:
        return False, [ReasonCode.STALE_DATA]
    if quality is DataQuality.INVALID:
        return False, [ReasonCode.INVALID_DATA]
    if quality is DataQuality.UNKNOWN:
        return False, [ReasonCode.STALE_DATA]
    return True, []


def filter_min_order(
    available_quote: float,
    mid_price: float | None,
    min_cost: float | None,
    min_amount: float | None,
) -> tuple[Feasibility, list[ReasonCode]]:
    reasons: list[ReasonCode] = []
    if mid_price is None or mid_price <= 0:
        return Feasibility.UNKNOWN, reasons
    if min_cost is not None and available_quote < min_cost:
        reasons.append(ReasonCode.MIN_ORDER_UNFEASIBLE)
        return Feasibility.ORDER_NOT_FEASIBLE, reasons
    if min_amount is not None and mid_price > 0 and available_quote / mid_price < min_amount:
        reasons.append(ReasonCode.MIN_ORDER_UNFEASIBLE)
        return Feasibility.ORDER_NOT_FEASIBLE, reasons
    if available_quote <= 0:
        # might still sell base
        return Feasibility.FEASIBLE, reasons
    return Feasibility.FEASIBLE, reasons


def filter_inactive(rm: ReachableMarket) -> tuple[bool, list[ReasonCode]]:
    if not rm.market.active:
        return False, [ReasonCode.MARKET_INACTIVE]
    return True, []


def edge_covers_costs(
    expected_return: float,
    spread_pct: float | None,
    fee_pct: float,
    slippage_pct: float,
) -> tuple[bool, list[ReasonCode]]:
    """True if |expected_return| exceeds estimated round-trip costs."""
    spread = (spread_pct or 0.0) / 100.0
    cost = (fee_pct / 100.0) * 2 + (slippage_pct / 100.0) + spread
    if abs(expected_return) <= cost:
        return False, [ReasonCode.FEE_EXCEEDS_EDGE]
    return True, []
