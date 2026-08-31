"""Graceful degradation under resource pressure / health / data-quality faults.

Inference always prioritized. Training deferred. Heavy ML shed first.
Never auto-promotes. Never enables LIVE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from .hardware import HardwareProfile, ResourceLimits


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DegradationDecision:
    mode: str  # FULL | REDUCED | MINIMAL | SAFE_ONLY
    allow_training: bool
    allow_heavy_ml: bool
    max_ensemble: int
    prefer_no_trade: bool
    reasons: list[str] = field(default_factory=list)
    decided_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allow_training": self.allow_training,
            "allow_heavy_ml": self.allow_heavy_ml,
            "max_ensemble": self.max_ensemble,
            "prefer_no_trade": self.prefer_no_trade,
            "reasons": list(self.reasons),
            "decided_at": self.decided_at,
        }


def evaluate_degradation(
    *,
    profile: Optional[HardwareProfile] = None,
    limits: Optional[ResourceLimits] = None,
    health_status: str = "UNKNOWN",
    data_quality_status: str = "OK",
    resource_pressure: bool = False,
    drift_restrict: bool = False,
) -> DegradationDecision:
    """Deterministic degradation ladder based on health + resources + data quality."""
    reasons: list[str] = []
    mode = "FULL"
    allow_training = True
    allow_heavy = True
    max_ens = 3
    no_trade = False

    # Profile floor
    if profile is not None:
        pname = profile.value if hasattr(profile, "value") else str(profile)
        if pname == "CONSERVATIVE":
            mode = "REDUCED"
            allow_heavy = False
            max_ens = 1
            reasons.append("profile_conservative")
        elif pname == "BALANCED":
            max_ens = min(max_ens, 3)
            allow_heavy = False  # neural still gated by capabilities
            reasons.append("profile_balanced")

    if limits is not None:
        if not getattr(limits, "training_allowed", True):
            allow_training = False
            reasons.append("limits_training_blocked")
        if getattr(limits, "inference_priority", True) and resource_pressure:
            allow_training = False
            reasons.append("inference_priority_under_pressure")
        max_ens = min(max_ens, int(getattr(limits, "max_ensemble_size", max_ens) or max_ens))

    if resource_pressure:
        if mode == "FULL":
            mode = "REDUCED"
        allow_heavy = False
        max_ens = min(max_ens, 1)
        allow_training = False
        reasons.append("resource_pressure")

    if data_quality_status == "FAIL":
        mode = "SAFE_ONLY"
        allow_training = False
        allow_heavy = False
        max_ens = 1
        no_trade = True
        reasons.append("data_quality_fail")
    elif data_quality_status == "WARN":
        if mode == "FULL":
            mode = "REDUCED"
        allow_heavy = False
        max_ens = min(max_ens, 1)
        reasons.append("data_quality_warn")

    if health_status == "CRITICAL":
        mode = "SAFE_ONLY"
        allow_training = False
        allow_heavy = False
        max_ens = 1
        no_trade = True
        reasons.append("health_critical")
    elif health_status == "DEGRADED":
        if mode == "FULL":
            mode = "REDUCED"
        allow_heavy = False
        max_ens = min(max_ens, 1)
        reasons.append("health_degraded")
    elif health_status == "UNKNOWN":
        if mode == "FULL":
            mode = "MINIMAL"
        allow_training = False
        max_ens = 1
        no_trade = True
        reasons.append("health_unknown")

    if drift_restrict:
        allow_training = allow_training  # retrain may still be eligible via scheduler
        max_ens = min(max_ens, 1)
        reasons.append("drift_restrict")

    # Clamp
    max_ens = max(1, min(max_ens, 5))

    return DegradationDecision(
        mode=mode,
        allow_training=allow_training,
        allow_heavy_ml=allow_heavy,
        max_ensemble=max_ens,
        prefer_no_trade=no_trade,
        reasons=reasons,
        decided_at=_utc_now(),
    )
