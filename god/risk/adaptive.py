"""Capital-Adaptive Risk Engine — risk% fixed; capital scales; broker constraints bind.

ADAPTIVE ≠ AGGRESSIVE.
- risk_percent is authoritative (never raised after losses)
- volume is ROUND-DOWN only
- min lot that exceeds risk budget ⇒ NO TRADE (never upsize past risk)
- no martingale / recovery multipliers
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from god.risk.account_snapshot import AccountSnapshot
from god.risk.broker_constraints import SymbolConstraints


def _floor_to_step(value: float, step: float) -> float:
    """Round DOWN to valid volume step. Never round up (would overshoot risk)."""
    if step <= 0:
        return 0.0
    if value <= 0:
        return 0.0
    n = int(value / step + 1e-12)  # floor
    return round(n * step, 10)


@dataclass
class ExposureLimits:
    """Portfolio / session risk caps. All optional defaults are fail-safe."""

    max_risk_per_trade_pct: float = 0.02  # hard ceiling on risk_pct input
    max_total_open_risk: float = 1e12  # absolute currency
    max_total_exposure_lots: float = 100.0
    max_concurrent_positions: int = 10
    max_daily_loss: float = 1e12
    max_drawdown_pct: float = 0.50
    max_margin_utilization: float = 0.90  # fraction of equity
    min_free_margin: float = 0.0
    min_margin_level: float = 0.0  # percent; 0 disables
    minimum_operational_equity: float = 1.0  # capital floor


@dataclass
class AdaptiveRiskRequest:
    snapshot: AccountSnapshot
    constraints: SymbolConstraints
    risk_pct: float  # e.g. 0.01 = 1% of equity
    stop_loss_distance: float  # absolute price distance
    spread_price: float = 0.0  # ask-bid in price units
    commission_per_lot: float = 0.0  # round-turn account currency
    existing_open_risk: float = 0.0
    existing_exposure_lots: float = 0.0
    open_positions: int = 0
    daily_loss: float = 0.0
    peak_equity: float = 0.0
    limits: Optional[ExposureLimits] = None
    max_cost_ratio: float = 0.50  # cost / risk_budget; above ⇒ NO TRADE


@dataclass(frozen=True)
class AdaptiveRiskResult:
    ok: bool
    volume: float = 0.0
    reason: str = ""
    risk_budget: float = 0.0  # equity * risk_pct
    raw_volume: float = 0.0
    feasible_volume: float = 0.0
    actual_worst_case_risk: float = 0.0
    estimated_margin: float = 0.0
    estimated_spread_cost: float = 0.0
    estimated_commission: float = 0.0
    estimated_total_cost: float = 0.0
    equity_used: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "volume": self.volume,
            "reason": self.reason,
            "risk_budget": self.risk_budget,
            "raw_volume": self.raw_volume,
            "feasible_volume": self.feasible_volume,
            "actual_worst_case_risk": self.actual_worst_case_risk,
            "estimated_margin": self.estimated_margin,
            "estimated_spread_cost": self.estimated_spread_cost,
            "estimated_commission": self.estimated_commission,
            "estimated_total_cost": self.estimated_total_cost,
            "equity_used": self.equity_used,
            "details": dict(self.details),
        }


class CapitalAdaptiveRiskEngine:
    """
    Transparent, auditable capital-adaptive sizing.

    Formula (primary):
      risk_budget = equity * risk_pct
      loss_per_lot = (stop_loss_distance / tick_size) * tick_value
      raw_volume   = risk_budget / loss_per_lot
      volume      = floor_to_step(raw_volume)  # ROUND DOWN
      actual_risk = volume * loss_per_lot

    If volume < volume_min:
      evaluate min-lot risk; if min-lot risk > risk_budget → NO TRADE
      (never force min lot past risk)

    No martingale. risk_pct is never increased by this engine.
    """

    def evaluate(self, req: AdaptiveRiskRequest) -> AdaptiveRiskResult:
        limits = req.limits or ExposureLimits()
        snap = req.snapshot
        cons = req.constraints
        details: dict[str, Any] = {}

        equity = float(snap.equity)
        details["equity"] = equity

        if equity < float(limits.minimum_operational_equity):
            return AdaptiveRiskResult(
                ok=False,
                reason="below_capital_floor",
                equity_used=equity,
                details=details,
            )

        risk_pct = float(req.risk_pct)
        if risk_pct <= 0:
            return AdaptiveRiskResult(ok=False, reason="invalid_risk_pct", equity_used=equity)
        if risk_pct > float(limits.max_risk_per_trade_pct):
            return AdaptiveRiskResult(
                ok=False,
                reason="risk_pct_exceeds_hard_cap",
                equity_used=equity,
                details={"risk_pct": risk_pct, "cap": limits.max_risk_per_trade_pct},
            )

        if int(req.open_positions) >= int(limits.max_concurrent_positions):
            return AdaptiveRiskResult(ok=False, reason="max_concurrent_positions", equity_used=equity)
        if float(req.daily_loss) >= float(limits.max_daily_loss):
            return AdaptiveRiskResult(ok=False, reason="max_daily_loss", equity_used=equity)
        if float(req.existing_open_risk) >= float(limits.max_total_open_risk):
            return AdaptiveRiskResult(ok=False, reason="max_total_open_risk", equity_used=equity)
        if float(req.existing_exposure_lots) >= float(limits.max_total_exposure_lots):
            return AdaptiveRiskResult(ok=False, reason="max_total_exposure", equity_used=equity)

        if limits.min_free_margin > 0 and snap.free_margin < limits.min_free_margin:
            return AdaptiveRiskResult(ok=False, reason="insufficient_free_margin", equity_used=equity)
        if limits.min_margin_level > 0 and snap.margin > 0:
            if snap.margin_level < limits.min_margin_level:
                return AdaptiveRiskResult(ok=False, reason="margin_level_too_low", equity_used=equity)

        if equity > 0 and limits.max_margin_utilization < 1.0:
            util = snap.margin / equity if equity else 1.0
            if util >= limits.max_margin_utilization:
                return AdaptiveRiskResult(ok=False, reason="max_margin_utilization", equity_used=equity)

        if req.peak_equity > 0 and limits.max_drawdown_pct < 1.0:
            dd = (req.peak_equity - equity) / req.peak_equity
            if dd >= limits.max_drawdown_pct:
                return AdaptiveRiskResult(ok=False, reason="max_drawdown", equity_used=equity)

        stop = float(req.stop_loss_distance)
        if stop <= 0:
            return AdaptiveRiskResult(ok=False, reason="invalid_stop_distance", equity_used=equity)
        tick_size = float(cons.tick_size)
        tick_value = float(cons.tick_value)
        if tick_size <= 0 or tick_value <= 0:
            return AdaptiveRiskResult(ok=False, reason="invalid_tick_geometry", equity_used=equity)

        risk_budget = equity * risk_pct
        ticks_to_stop = stop / tick_size
        loss_per_lot = ticks_to_stop * tick_value
        if loss_per_lot <= 0:
            return AdaptiveRiskResult(
                ok=False,
                reason="invalid_loss_per_lot",
                risk_budget=risk_budget,
                equity_used=equity,
            )

        raw_volume = risk_budget / loss_per_lot
        vol = _floor_to_step(raw_volume, float(cons.volume_step))
        details.update(
            {
                "risk_pct": risk_pct,
                "loss_per_lot": loss_per_lot,
                "ticks_to_stop": ticks_to_stop,
                "volume_min": cons.volume_min,
                "volume_max": cons.volume_max,
                "volume_step": cons.volume_step,
            }
        )

        if vol > float(cons.volume_max):
            vol = _floor_to_step(float(cons.volume_max), float(cons.volume_step))

        if vol < float(cons.volume_min):
            min_lot_risk = float(cons.volume_min) * loss_per_lot
            details["min_lot_risk"] = min_lot_risk
            if min_lot_risk > risk_budget + 1e-12:
                return AdaptiveRiskResult(
                    ok=False,
                    reason="min_lot_exceeds_risk_budget",
                    risk_budget=risk_budget,
                    raw_volume=raw_volume,
                    feasible_volume=0.0,
                    actual_worst_case_risk=min_lot_risk,
                    equity_used=equity,
                    details=details,
                )
            vol = float(cons.volume_min)

        if vol <= 0:
            return AdaptiveRiskResult(
                ok=False,
                reason="volume_zero",
                risk_budget=risk_budget,
                raw_volume=raw_volume,
                equity_used=equity,
                details=details,
            )

        actual_risk = vol * loss_per_lot
        if actual_risk > risk_budget + 1e-9:
            return AdaptiveRiskResult(
                ok=False,
                reason="actual_risk_exceeds_budget",
                risk_budget=risk_budget,
                raw_volume=raw_volume,
                feasible_volume=vol,
                actual_worst_case_risk=actual_risk,
                equity_used=equity,
                details=details,
            )

        if actual_risk + float(req.existing_open_risk) > float(limits.max_total_open_risk):
            return AdaptiveRiskResult(
                ok=False,
                reason="total_open_risk_exceeded",
                risk_budget=risk_budget,
                actual_worst_case_risk=actual_risk,
                equity_used=equity,
                details=details,
            )

        margin_per_lot = float(cons.margin_initial)
        if margin_per_lot <= 0 and snap.leverage and snap.leverage > 0:
            margin_per_lot = float(cons.contract_size) / float(snap.leverage)
        estimated_margin = vol * margin_per_lot
        if estimated_margin > 0 and estimated_margin > snap.free_margin + 1e-9:
            return AdaptiveRiskResult(
                ok=False,
                reason="insufficient_margin",
                risk_budget=risk_budget,
                feasible_volume=vol,
                actual_worst_case_risk=actual_risk,
                estimated_margin=estimated_margin,
                equity_used=equity,
                details=details,
            )

        spread_price = max(0.0, float(req.spread_price))
        spread_cost = 0.0
        if tick_size > 0 and spread_price > 0:
            spread_cost = (spread_price / tick_size) * tick_value * vol
        commission = float(req.commission_per_lot) * vol
        total_cost = spread_cost + commission
        if risk_budget > 0 and total_cost / risk_budget > float(req.max_cost_ratio):
            return AdaptiveRiskResult(
                ok=False,
                reason="excessive_cost_ratio",
                risk_budget=risk_budget,
                feasible_volume=vol,
                actual_worst_case_risk=actual_risk,
                estimated_margin=estimated_margin,
                estimated_spread_cost=spread_cost,
                estimated_commission=commission,
                estimated_total_cost=total_cost,
                equity_used=equity,
                details=details,
            )

        return AdaptiveRiskResult(
            ok=True,
            volume=float(vol),
            reason="ok",
            risk_budget=risk_budget,
            raw_volume=raw_volume,
            feasible_volume=float(vol),
            actual_worst_case_risk=actual_risk,
            estimated_margin=estimated_margin,
            estimated_spread_cost=spread_cost,
            estimated_commission=commission,
            estimated_total_cost=total_cost,
            equity_used=equity,
            details=details,
        )
