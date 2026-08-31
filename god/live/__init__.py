"""LIVE execution control — arming, preflight, kill switch, risk gate.

LIVE READY requires real broker + preflight PASS + explicit arm or
administrative autonomous policy resume after restart.
Default: DISABLED. Operator acceptance does not bypass safety without policy.
"""

from .models import (
    HardRiskLimits,
    LiveExecutionState,
    LiveMode,
    LivePrerequisites,
    LiveValidationState,
    PreflightStatus,
)
from .preflight import run_preflight
from .authorization import LiveAuthorizationGate, LiveArmResult
from .controller import LiveExecutionController
from .autonomous_policy import (
    AutonomousTradingPolicy,
    load_policy,
    save_policy,
    enable_autonomous_live,
    enable_autonomous_paper,
    default_policy_path,
)
from .autonomous_runtime import run_autonomous_startup, run_autonomous_runtime

__all__ = [
    "HardRiskLimits",
    "LiveExecutionState",
    "LiveMode",
    "LivePrerequisites",
    "LiveValidationState",
    "PreflightStatus",
    "run_preflight",
    "LiveAuthorizationGate",
    "LiveArmResult",
    "LiveExecutionController",
    "AutonomousTradingPolicy",
    "load_policy",
    "save_policy",
    "enable_autonomous_live",
    "enable_autonomous_paper",
    "default_policy_path",
    "run_autonomous_startup",
    "run_autonomous_runtime",
]
