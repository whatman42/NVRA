"""Risk policy configuration.

Hardware profile must NEVER modify these limits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Configurable safety limits (independent of hardware)."""

    # Position / exposure (fractions of equity unless noted)
    max_position_pct: float = 5.0  # % of equity per position
    max_symbol_exposure_pct: float = 10.0
    max_exchange_exposure_pct: float = 50.0
    max_portfolio_exposure_pct: float = 25.0
    max_concurrent_positions: int = 5

    # Loss limits
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 10.0
    max_consecutive_losses: int = 5

    # Cost assumptions when exchange fees unknown
    default_taker_fee_pct: float = 0.1  # 0.1%
    default_slippage_pct: float = 0.05  # 0.05%

    # Market data quality
    reject_stale_data: bool = True
    reject_invalid_data: bool = True
    reject_unknown_data: bool = True

    # Sizing
    min_notional: float = 0.0  # additional floor beyond exchange min
    risk_per_trade_pct: float = 1.0  # % equity risked per trade (stop-based)

    def validate(self) -> None:
        for name, val in (
            ("max_position_pct", self.max_position_pct),
            ("max_symbol_exposure_pct", self.max_symbol_exposure_pct),
            ("max_exchange_exposure_pct", self.max_exchange_exposure_pct),
            ("max_portfolio_exposure_pct", self.max_portfolio_exposure_pct),
            ("max_daily_loss_pct", self.max_daily_loss_pct),
            ("max_drawdown_pct", self.max_drawdown_pct),
        ):
            if not (0.0 < val <= 100.0):
                raise ValueError(f"{name} must be in (0, 100]")
        if self.max_concurrent_positions < 0:
            raise ValueError("max_concurrent_positions must be >= 0")
        if self.default_taker_fee_pct < 0 or self.default_slippage_pct < 0:
            raise ValueError("fee/slippage defaults must be >= 0")
