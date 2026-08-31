"""LIVE execution state machine. Fail-closed. ARM required. No auto-LIVE on start."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class LiveMode(str, Enum):
    DEMO = "DEMO"
    PAPER = "PAPER"
    LIVE = "LIVE"


class LiveExecutionState(str, Enum):
    DISABLED = "DISABLED"
    READY = "READY"
    ARMING = "ARMING"
    ARMED = "ARMED"
    EXECUTING = "EXECUTING"
    MONITORING = "MONITORING"
    DEGRADED = "DEGRADED"
    HALTED = "HALTED"
    BLOCKED = "BLOCKED"


class LiveValidationState(str, Enum):
    """Product-facing LIVE validation mode (fail-closed).

    DEMO           — paper/demo; LIVE arm rejected.
    LIVE_DISABLED  — default LIVE path; cannot submit LIVE.
    LIVE_READY     — all prerequisites true; not yet armed.
    LIVE_ARMED     — prerequisites + explicit operator ARM.
    SAFE_MODE      — recovery/fault; LIVE orders blocked.
    """

    DEMO = "DEMO"
    LIVE_DISABLED = "LIVE_DISABLED"
    LIVE_READY = "LIVE_READY"
    LIVE_ARMED = "LIVE_ARMED"
    SAFE_MODE = "SAFE_MODE"


class PreflightStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class HardRiskLimits:
    max_position_size: float = 0.01
    max_total_exposure: float = 0.05
    max_daily_loss: float = 0.01
    max_drawdown: float = 0.05
    max_risk_per_trade: float = 0.005
    max_open_positions: int = 1
    max_order_notional: float = 100.0
    max_slippage: float = 0.001
    max_spread: float = 0.0005
    max_consecutive_losses: int = 3

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_position_size": self.max_position_size,
            "max_total_exposure": self.max_total_exposure,
            "max_daily_loss": self.max_daily_loss,
            "max_drawdown": self.max_drawdown,
            "max_risk_per_trade": self.max_risk_per_trade,
            "max_open_positions": self.max_open_positions,
            "max_order_notional": self.max_order_notional,
            "max_slippage": self.max_slippage,
            "max_spread": self.max_spread,
            "max_consecutive_losses": self.max_consecutive_losses,
        }


@dataclass
class PreflightReport:
    overall: PreflightStatus
    checks: dict[str, PreflightStatus] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall": self.overall.value,
            "checks": {k: v.value for k, v in self.checks.items()},
            "reasons": list(self.reasons),
        }


@dataclass
class LivePrerequisites:
    """LIVE arm prerequisites. All must be True for LIVE_READY. Defaults False."""

    operator_authorized: bool = False
    license_valid: bool = False
    device_valid: bool = False
    credentials_valid: bool = False
    broker_connected: bool = False
    state_loaded: bool = False
    reconciliation_pass: bool = False
    risk_governor_ready: bool = False
    startup_ready: bool = False

    def missing(self) -> list[str]:
        return [k for k, v in self.as_dict().items() if not v]

    def all_satisfied(self) -> bool:
        return not self.missing()

    def as_dict(self) -> dict[str, bool]:
        return {
            "operator_authorized": self.operator_authorized,
            "license_valid": self.license_valid,
            "device_valid": self.device_valid,
            "credentials_valid": self.credentials_valid,
            "broker_connected": self.broker_connected,
            "state_loaded": self.state_loaded,
            "reconciliation_pass": self.reconciliation_pass,
            "risk_governor_ready": self.risk_governor_ready,
            "startup_ready": self.startup_ready,
        }


MANDATORY_PREFLIGHT = (
    "broker_credentials",
    "broker_connection",
    "account_authenticated",
    "account_identity",
    "trading_permissions",
    "market_data_live",
    "clock_sync",
    "symbol_mapping",
    "contract_specs",
    "price_fresh",
    "portfolio_sync",
    "positions_sync",
    "orders_sync",
    "risk_engine",
    "risk_limits",
    "execution_engine",
    "model_loaded",
    "model_compatible",
    "feature_schema",
    "state_snapshot",
    "audit_logging",
    "kill_switch",
)
