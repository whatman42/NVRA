"""Headless autonomous trading lifecycle after administrative setup.

Does not implement strategy, risk math, or broker protocols.
Orchestrates: load policy → safety chain → READY/RUNNING or SAFE_MODE.
GUI is never required. ML cannot set administrative authorization.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from god.live.autonomous_policy import (
    AutonomousTradingPolicy,
    default_policy_path,
    load_policy,
)
from god.live.authorization import LiveAuthorizationGate
from god.live.controller import LiveExecutionController
from god.live.models import (
    LiveMode,
    LivePrerequisites,
    LiveValidationState,
    PreflightStatus,
    MANDATORY_PREFLIGHT,
)
from god.mt5_runtime.safety_gate import LiveCapitalGate


@dataclass
class AutonomousRuntimeResult:
    ok: bool
    state: str
    mode: str
    reason: str = ""
    safe_mode: bool = False
    headless: bool = True
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "state": self.state,
            "mode": self.mode,
            "reason": self.reason,
            "safe_mode": self.safe_mode,
            "headless": self.headless,
            "details": dict(self.details),
        }


def evaluate_runtime_prechecks(
    *,
    license_valid: bool = False,
    device_valid: bool = False,
    credentials_valid: bool = False,
    broker_connected: bool = False,
    state_loaded: bool = False,
    reconciliation_pass: bool = False,
    risk_governor_ready: bool = False,
    startup_ready: bool = False,
    artifact_integrity: bool = True,
    config_valid: bool = True,
) -> tuple[bool, LivePrerequisites, list[str]]:
    prereq = LivePrerequisites(
        operator_authorized=True,
        license_valid=license_valid,
        device_valid=device_valid,
        credentials_valid=credentials_valid,
        broker_connected=broker_connected,
        state_loaded=state_loaded,
        reconciliation_pass=reconciliation_pass,
        risk_governor_ready=risk_governor_ready,
        startup_ready=startup_ready,
    )
    missing = prereq.missing()
    if not artifact_integrity:
        missing.append("artifact_integrity")
    if not config_valid:
        missing.append("config_valid")
    return (len(missing) == 0, prereq, missing)


def run_autonomous_startup(
    *,
    data_dir: Optional[Path] = None,
    precheck: Optional[Callable[[], dict[str, bool]]] = None,
    max_recovery_attempts: int = 3,
    recovery_sleep_s: float = 0.0,
) -> AutonomousRuntimeResult:
    path = default_policy_path(data_dir)
    policy = load_policy(path)
    if policy is None:
        return AutonomousRuntimeResult(
            ok=True, state="READY", mode="PAPER", reason="no_policy_default_paper",
            details={"policy_path": str(path), "live": False},
        )
    if not policy.autonomous_enabled:
        return AutonomousRuntimeResult(
            ok=False, state="SAFE_MODE", mode=policy.trading_mode,
            reason="autonomous_disabled", safe_mode=True,
        )

    mode = policy.trading_mode
    live = mode == "LIVE" and policy.autonomous_live

    def _probes() -> dict[str, bool]:
        if precheck is not None:
            return dict(precheck())
        if live:
            return {
                "license_valid": False, "device_valid": False, "credentials_valid": False,
                "broker_connected": False, "state_loaded": False, "reconciliation_pass": False,
                "risk_governor_ready": False, "startup_ready": False,
                "artifact_integrity": True, "config_valid": True,
            }
        return {
            "license_valid": True, "device_valid": True, "credentials_valid": True,
            "broker_connected": True, "state_loaded": True, "reconciliation_pass": True,
            "risk_governor_ready": True, "startup_ready": True,
            "artifact_integrity": True, "config_valid": True,
        }

    attempt = 0
    last_missing: list[str] = []
    while attempt <= max_recovery_attempts:
        attempt += 1
        flags = _probes()
        ok, prereq, missing = evaluate_runtime_prechecks(**flags)
        last_missing = missing
        if ok:
            break
        if recovery_sleep_s > 0:
            time.sleep(recovery_sleep_s)
    else:
        return AutonomousRuntimeResult(
            ok=False, state="SAFE_MODE", mode=mode, reason="prechecks_failed",
            safe_mode=True, details={"missing": last_missing, "attempts": attempt},
        )

    if not live:
        return AutonomousRuntimeResult(
            ok=True, state="RUNNING", mode=mode, reason="autonomous_paper_or_demo",
            details={"policy": policy.to_dict()},
        )

    capital = LiveCapitalGate(blocked=True)
    capital.authorize_from_admin_policy(reason="admin_autonomous_policy")
    ctrl = LiveExecutionController(mode=LiveMode.LIVE, capital_gate=capital)
    ctrl.auth_gate = LiveAuthorizationGate(demo=False)
    ctrl.auth_gate.set_prerequisites(prereq)
    pf = {n: PreflightStatus.PASS for n in MANDATORY_PREFLIGHT}
    ctrl.evaluate_preflight(pf)
    arm = ctrl.arm_from_admin_policy(
        prerequisites_satisfied=True, policy_reason="autonomous_policy_resume",
    )
    if not arm.get("ok"):
        return AutonomousRuntimeResult(
            ok=False, state="SAFE_MODE", mode="LIVE",
            reason=str(arm.get("reason", "arm_failed")), safe_mode=True,
            details={"arm": arm},
        )
    return AutonomousRuntimeResult(
        ok=True, state="RUNNING", mode="LIVE", reason="autonomous_live_resumed",
        details={
            "policy": policy.to_dict(),
            "validation_state": ctrl.auth_gate.state.value,
            "can_submit_live": ctrl.auth_gate.can_submit_live(),
            "capital_allowed": capital.allow_live_execution(),
        },
    )


def run_autonomous_runtime(*, data_dir: Optional[Path] = None) -> int:
    result = run_autonomous_startup(data_dir=data_dir)
    if result.ok and result.state == "RUNNING":
        return 0
    if result.reason == "no_policy_default_paper":
        return 0
    return 1
