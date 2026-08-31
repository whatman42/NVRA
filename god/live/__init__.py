"""LIVE execution control — arming, preflight, kill switch, risk gate.

LIVE READY requires real broker + preflight PASS + explicit arm.
Default: DISABLED. Operator acceptance does not bypass safety.
"""

from .models import HardRiskLimits, LiveExecutionState, LiveMode, PreflightStatus
from .preflight import run_preflight
from .controller import LiveExecutionController

__all__ = [
    "HardRiskLimits",
    "LiveExecutionState",
    "LiveMode",
    "PreflightStatus",
    "run_preflight",
    "LiveExecutionController",
]
