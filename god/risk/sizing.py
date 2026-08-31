"""Position sizing — equity × risk% / stop distance. Fail-closed.

No default 0.01 production dependency. Missing inputs → reject (volume=0).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class PositionSizeRequest:
    equity: float
    risk_pct: float  # e.g. 0.01 = 1%
    stop_distance: float  # absolute price distance to SL
    tick_size: float = 0.0001
    tick_value: float = 1.0  # value per tick per 1.0 lot
    volume_min: float = 0.01
    volume_max: float = 100.0
    volume_step: float = 0.01
    contract_size: float = 100_000.0  # standard FX lot


@dataclass(frozen=True)
class PositionSizeResult:
    ok: bool
    volume: float
    reason: str
    risk_amount: float = 0.0
    raw_volume: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "volume": self.volume,
            "reason": self.reason,
            "risk_amount": self.risk_amount,
            "raw_volume": self.raw_volume,
        }


def _round_step(value: float, step: float) -> float:
    if step <= 0:
        return value
    # floor to step
    n = int(value / step + 1e-12)
    return round(n * step, 8)


def compute_position_size(req: PositionSizeRequest) -> PositionSizeResult:
    """
    volume ≈ (equity * risk_pct) / (stop_distance / tick_size * tick_value)

    Fail-closed when equity/risk/stop/tick invalid.
    """
    if req.equity is None or req.equity <= 0:
        return PositionSizeResult(False, 0.0, "invalid_equity")
    if req.risk_pct is None or req.risk_pct <= 0 or req.risk_pct > 0.10:
        # hard cap risk_pct at 10% as safety
        return PositionSizeResult(False, 0.0, "invalid_risk_pct")
    if req.stop_distance is None or req.stop_distance <= 0:
        return PositionSizeResult(False, 0.0, "invalid_stop_distance")
    if req.tick_size is None or req.tick_size <= 0:
        return PositionSizeResult(False, 0.0, "invalid_tick_size")
    if req.tick_value is None or req.tick_value <= 0:
        return PositionSizeResult(False, 0.0, "invalid_tick_value")
    if req.volume_min is None or req.volume_min <= 0:
        return PositionSizeResult(False, 0.0, "invalid_volume_min")
    if req.volume_max is not None and req.volume_max < req.volume_min:
        return PositionSizeResult(False, 0.0, "invalid_volume_max")
    if req.volume_step is None or req.volume_step <= 0:
        return PositionSizeResult(False, 0.0, "invalid_volume_step")

    risk_amount = float(req.equity) * float(req.risk_pct)
    ticks_to_stop = float(req.stop_distance) / float(req.tick_size)
    loss_per_lot = ticks_to_stop * float(req.tick_value)
    if loss_per_lot <= 0:
        return PositionSizeResult(False, 0.0, "invalid_loss_per_lot", risk_amount=risk_amount)

    raw = risk_amount / loss_per_lot
    vol = _round_step(raw, float(req.volume_step))
    if vol < float(req.volume_min):
        return PositionSizeResult(
            False,
            0.0,
            "below_volume_min",
            risk_amount=risk_amount,
            raw_volume=raw,
        )
    vmax = float(req.volume_max) if req.volume_max is not None else vol
    if vol > vmax:
        vol = _round_step(vmax, float(req.volume_step))
    if vol <= 0:
        return PositionSizeResult(False, 0.0, "volume_zero", risk_amount=risk_amount, raw_volume=raw)

    return PositionSizeResult(
        ok=True,
        volume=float(vol),
        reason="ok",
        risk_amount=risk_amount,
        raw_volume=raw,
    )
