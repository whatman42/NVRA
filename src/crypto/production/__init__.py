"""Production hardening & LIVE safety gate (Phase 15).

Default mode remains PAPER. CI never places LIVE orders.
SOFTWARE GREEN ≠ PRODUCTION LIVE GO.
"""

from crypto.production.canary import CanaryPhase, CanaryState
from crypto.production.gates import (
    GateCheck,
    GateSeverity,
    LiveDecision,
    ProductionGate,
    ProductionGateReport,
)
from crypto.production.kill import KillAction, KillSwitch
from crypto.production.limits import MicroCapitalLimits, clamp_to_hard_ceiling
from crypto.production.profile import ExecutionProfiler, ExecutionProfileSample
from crypto.production.security import scan_text_for_secrets, scan_tree_for_secrets

__all__ = [
    "ProductionGate",
    "ProductionGateReport",
    "GateCheck",
    "GateSeverity",
    "LiveDecision",
    "MicroCapitalLimits",
    "clamp_to_hard_ceiling",
    "CanaryState",
    "CanaryPhase",
    "ExecutionProfiler",
    "ExecutionProfileSample",
    "KillSwitch",
    "KillAction",
    "scan_text_for_secrets",
    "scan_tree_for_secrets",
]
