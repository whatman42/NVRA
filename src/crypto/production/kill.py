"""Independent kill conditions — additive to RiskEngine, not a replacement."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto


class KillAction(Enum):
    NONE = auto()
    BLOCK_NEW_ENTRIES = auto()
    SAFE_MODE = auto()


@dataclass
class KillCondition:
    name: str
    triggered: bool
    action: KillAction
    detail: str = ""


@dataclass
class KillSwitch:
    """Evaluates hard safety triggers. Does not mutate RiskPolicy."""

    daily_loss: float = 0.0
    max_daily_loss: float = 5.0
    drawdown_pct: float = 0.0
    max_drawdown_pct: float = 3.0
    exchange_rejections: int = 0
    max_rejections: int = 5
    slippage_bps: float = 0.0
    max_slippage_bps: float = 50.0
    stale_data: bool = False
    recon_mismatch: bool = False
    permission_mismatch: bool = False
    time_sync_fail: bool = False
    db_integrity_fail: bool = False
    recovery_storm: bool = False
    resource_critical: bool = False
    latency_ms: float = 0.0
    max_latency_ms: float = 3000.0
    conditions: list[KillCondition] = field(default_factory=list)

    def evaluate(self) -> KillAction:
        self.conditions.clear()
        action = KillAction.NONE

        def trig(name: str, hit: bool, act: KillAction, detail: str = "") -> None:
            nonlocal action
            self.conditions.append(
                KillCondition(name, hit, act if hit else KillAction.NONE, detail)
            )
            if hit and act.value > action.value:
                action = act

        trig("daily_loss", self.daily_loss >= self.max_daily_loss, KillAction.SAFE_MODE)
        trig("drawdown", self.drawdown_pct >= self.max_drawdown_pct, KillAction.SAFE_MODE)
        trig(
            "rejections",
            self.exchange_rejections >= self.max_rejections,
            KillAction.BLOCK_NEW_ENTRIES,
        )
        trig(
            "slippage",
            self.slippage_bps >= self.max_slippage_bps,
            KillAction.BLOCK_NEW_ENTRIES,
        )
        trig("stale_data", self.stale_data, KillAction.BLOCK_NEW_ENTRIES)
        trig("recon_mismatch", self.recon_mismatch, KillAction.SAFE_MODE)
        trig("permission", self.permission_mismatch, KillAction.SAFE_MODE)
        trig("time_sync", self.time_sync_fail, KillAction.BLOCK_NEW_ENTRIES)
        trig("db_integrity", self.db_integrity_fail, KillAction.SAFE_MODE)
        trig("recovery_storm", self.recovery_storm, KillAction.SAFE_MODE)
        trig("resource", self.resource_critical, KillAction.BLOCK_NEW_ENTRIES)
        trig(
            "latency",
            self.latency_ms >= self.max_latency_ms,
            KillAction.BLOCK_NEW_ENTRIES,
        )
        return action
