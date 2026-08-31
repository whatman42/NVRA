"""Micro-capital / LIVE canary hard ceilings — not RiskPolicy, additive safety."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MicroCapitalLimits:
    """Hard ceilings for TINY_CAPITAL_MODE. Not disableable via Telegram."""

    enabled: bool = True
    max_order_notional: float = 15.0  # quote currency
    max_total_exposure: float = 50.0
    max_live_orders: int = 1
    max_daily_loss: float = 5.0
    max_drawdown_pct: float = 3.0
    max_slippage_bps: float = 50.0
    max_latency_ms: float = 3000.0
    max_time_skew_ms: int = 5000

    def validate(self) -> None:
        if self.max_order_notional <= 0:
            raise ValueError("max_order_notional must be > 0")
        if self.max_live_orders < 1:
            raise ValueError("max_live_orders must be >= 1")
        if self.max_order_notional > 500:
            raise ValueError("hard ceiling: max_order_notional cannot exceed 500 in canary")
        if self.max_total_exposure > 2000:
            raise ValueError("hard ceiling: max_total_exposure cannot exceed 2000 in canary")


# Absolute software ceilings — cannot be raised by config without code change
HARD_CEILING_ORDER_NOTIONAL = 500.0
HARD_CEILING_EXPOSURE = 2000.0


def clamp_to_hard_ceiling(limits: MicroCapitalLimits) -> MicroCapitalLimits:
    return MicroCapitalLimits(
        enabled=limits.enabled,
        max_order_notional=min(limits.max_order_notional, HARD_CEILING_ORDER_NOTIONAL),
        max_total_exposure=min(limits.max_total_exposure, HARD_CEILING_EXPOSURE),
        max_live_orders=min(limits.max_live_orders, 3),
        max_daily_loss=limits.max_daily_loss,
        max_drawdown_pct=limits.max_drawdown_pct,
        max_slippage_bps=limits.max_slippage_bps,
        max_latency_ms=limits.max_latency_ms,
        max_time_skew_ms=limits.max_time_skew_ms,
    )
