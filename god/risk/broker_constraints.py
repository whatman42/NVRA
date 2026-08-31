"""Broker / symbol constraint discovery — never hardcode production limits.

Missing or invalid constraints ⇒ NO TRADE.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class SymbolConstraints:
    symbol: str
    volume_min: float
    volume_max: float
    volume_step: float
    contract_size: float = 100_000.0
    tick_size: float = 0.00001
    tick_value: float = 1.0
    margin_initial: float = 0.0  # margin required per 1.0 lot (account currency)
    trade_mode: str = "FULL"  # FULL | CLOSE_ONLY | DISABLED
    filling_mode: str = "IOC"
    digits: int = 5
    point: float = 0.00001
    spread_points: float = 0.0
    stops_level: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "volume_min": self.volume_min,
            "volume_max": self.volume_max,
            "volume_step": self.volume_step,
            "contract_size": self.contract_size,
            "tick_size": self.tick_size,
            "tick_value": self.tick_value,
            "margin_initial": self.margin_initial,
            "trade_mode": self.trade_mode,
            "filling_mode": self.filling_mode,
            "digits": self.digits,
            "point": self.point,
            "spread_points": self.spread_points,
            "stops_level": self.stops_level,
        }


@dataclass(frozen=True)
class ConstraintsValidation:
    ok: bool
    reasons: tuple[str, ...] = ()
    constraints: Optional[SymbolConstraints] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "constraints": self.constraints.to_dict() if self.constraints else None,
        }


def validate_symbol_constraints(c: SymbolConstraints) -> ConstraintsValidation:
    reasons: list[str] = []
    if not c.symbol:
        reasons.append("missing_symbol")
    if c.volume_min is None or c.volume_min <= 0:
        reasons.append("invalid_volume_min")
    if c.volume_max is None or c.volume_max < c.volume_min:
        reasons.append("invalid_volume_max")
    if c.volume_step is None or c.volume_step <= 0:
        reasons.append("invalid_volume_step")
    if c.tick_size is None or c.tick_size <= 0:
        reasons.append("invalid_tick_size")
    if c.tick_value is None or c.tick_value <= 0:
        reasons.append("invalid_tick_value")
    if c.contract_size is None or c.contract_size <= 0:
        reasons.append("invalid_contract_size")
    if c.trade_mode and c.trade_mode.upper() in ("DISABLED", "CLOSE_ONLY", "NONE"):
        if c.trade_mode.upper() == "DISABLED":
            reasons.append("trade_mode_disabled")
        elif c.trade_mode.upper() == "CLOSE_ONLY":
            reasons.append("trade_mode_close_only")
    ok = len(reasons) == 0
    return ConstraintsValidation(ok=ok, reasons=tuple(reasons), constraints=c)


def constraints_from_dict(symbol: str, data: dict[str, Any]) -> ConstraintsValidation:
    """Build constraints from broker-reported dict; missing keys ⇒ invalid."""
    required = ("volume_min", "volume_max", "volume_step", "tick_size", "tick_value")
    missing = [k for k in required if k not in data or data[k] is None]
    if missing:
        return ConstraintsValidation(
            ok=False,
            reasons=tuple(f"missing_{k}" for k in missing),
            constraints=None,
        )
    try:
        c = SymbolConstraints(
            symbol=symbol,
            volume_min=float(data["volume_min"]),
            volume_max=float(data["volume_max"]),
            volume_step=float(data["volume_step"]),
            contract_size=float(data.get("contract_size", 100_000.0)),
            tick_size=float(data["tick_size"]),
            tick_value=float(data["tick_value"]),
            margin_initial=float(data.get("margin_initial", 0.0) or 0.0),
            trade_mode=str(data.get("trade_mode", "FULL") or "FULL"),
            filling_mode=str(data.get("filling_mode", "IOC") or "IOC"),
            digits=int(data.get("digits", 5) or 5),
            point=float(data.get("point", data["tick_size"]) or data["tick_size"]),
            spread_points=float(data.get("spread_points", 0.0) or 0.0),
            stops_level=int(data.get("stops_level", 0) or 0),
        )
    except (TypeError, ValueError) as e:
        return ConstraintsValidation(ok=False, reasons=(f"parse_error:{e}",))
    return validate_symbol_constraints(c)
