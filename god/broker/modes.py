"""Explicit broker execution modes with fail-closed real-trading authorization.

Modes are per broker: DEMO or REAL. REAL requires three independent conditions:
configuration says REAL, NVRA_REAL_TRADING_ENABLE=true, and the exact confirmation
phrase is supplied. No code path auto-promotes DEMO to REAL.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum


class BrokerMode(str, Enum):
    DEMO = "DEMO"
    REAL = "REAL"


REAL_CONFIRMATION = "I_UNDERSTAND_REAL_TRADING"


@dataclass(frozen=True)
class BrokerModePolicy:
    broker: str
    mode: BrokerMode = BrokerMode.DEMO
    sandbox: bool = True
    allow_real: bool = False

    def validate(self) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if self.mode is BrokerMode.DEMO:
            return True, ()
        if not self.allow_real:
            reasons.append("real_mode_disabled_by_policy")
        if os.getenv("NVRA_REAL_TRADING_ENABLE", "0").lower() not in {"1", "true", "yes"}:
            reasons.append("NVRA_REAL_TRADING_ENABLE_not_set")
        if os.getenv("NVRA_REAL_TRADING_CONFIRM", "") != REAL_CONFIRMATION:
            reasons.append("real_trading_confirmation_missing")
        return not reasons, tuple(reasons)


def policy_from_env(broker: str, default: BrokerMode = BrokerMode.DEMO) -> BrokerModePolicy:
    raw = os.getenv(f"NVRA_{broker.upper()}_MODE", default.value).upper()
    try:
        mode = BrokerMode(raw)
    except ValueError:
        mode = BrokerMode.DEMO
    sandbox_default = mode is BrokerMode.DEMO
    sandbox = os.getenv(f"NVRA_{broker.upper()}_SANDBOX", "1" if sandbox_default else "0").lower() in {"1", "true", "yes"}
    allow_real = os.getenv(f"NVRA_{broker.upper()}_ALLOW_REAL", "0").lower() in {"1", "true", "yes"}
    return BrokerModePolicy(broker=broker, mode=mode, sandbox=sandbox, allow_real=allow_real)
