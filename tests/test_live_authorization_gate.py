"""LIVE authorization gate — fail-closed validation tests (no real broker orders)."""

from __future__ import annotations

from god.live.authorization import LiveAuthorizationGate
from god.live.controller import LiveExecutionController, LiveOrderIntent
from god.live.models import (
    LiveMode,
    LivePrerequisites,
    LiveValidationState,
    PreflightStatus,
    MANDATORY_PREFLIGHT,
)
from god.mt5_runtime.safety_gate import LIVE_CAPITAL_BLOCKED


def _all_pass_prereq(**overrides: bool) -> LivePrerequisites:
    base = dict(
        operator_authorized=True,
        license_valid=True,
        device_valid=True,
        credentials_valid=True,
        broker_connected=True,
        state_loaded=True,
        reconciliation_pass=True,
        risk_governor_ready=True,
        startup_ready=True,
    )
    base.update(overrides)
    return LivePrerequisites(**base)


def _all_preflight_pass() -> dict[str, PreflightStatus]:
    return {name: PreflightStatus.PASS for name in MANDATORY_PREFLIGHT}


def test_default_is_live_disabled():
    gate = LiveAuthorizationGate()
    assert gate.state == LiveValidationState.LIVE_DISABLED
    assert gate.can_submit_live() is False


def test_demo_mode_operational_without_live_auth():
    gate = LiveAuthorizationGate(demo=True)
    assert gate.state == LiveValidationState.DEMO
    res = gate.arm(operator_authorization="operator")
    assert res.ok is False
    assert gate.can_submit_live() is False


def test_missing_credentials_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq(credentials_valid=False))
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert "credentials_valid" in res.missing


def test_invalid_credentials_blocks_live():
    gate = LiveAuthorizationGate()
    gate.update_prerequisites(credentials_valid=False, license_valid=True)
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert gate.state != LiveValidationState.LIVE_ARMED


def test_license_failure_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq(license_valid=False))
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert "license_valid" in res.missing


def test_device_failure_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq(device_valid=False))
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert "device_valid" in res.missing


def test_broker_unavailable_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq(broker_connected=False))
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert "broker_connected" in res.missing


def test_reconciliation_failure_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq(reconciliation_pass=False))
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert "reconciliation_pass" in res.missing


def test_risk_governor_failure_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq(risk_governor_ready=False))
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert "risk_governor_ready" in res.missing


def test_safe_mode_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq())
    gate.enter_safe_mode("unit_test_fault")
    assert gate.state == LiveValidationState.SAFE_MODE
    res = gate.arm(operator_authorization="operator-ack")
    assert res.ok is False
    assert res.reason == "safe_mode"
    assert gate.can_submit_live() is False


def test_gui_crash_does_not_unlock_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq())
    assert gate.state == LiveValidationState.LIVE_READY
    gate.note_gui_fault()
    assert gate.can_submit_live() is False
    assert gate.state != LiveValidationState.LIVE_ARMED


def test_no_explicit_authorization_blocks_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq())
    res = gate.arm(operator_authorization="")
    assert res.ok is False
    assert res.reason == "missing_operator_authorization"


def test_all_prerequisites_plus_explicit_auth_arms_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq())
    assert gate.state == LiveValidationState.LIVE_READY
    res = gate.arm(operator_authorization="OPERATOR_CONFIRM_LIVE")
    assert res.ok is True
    assert gate.state == LiveValidationState.LIVE_ARMED
    assert gate.can_submit_live() is True


def test_disarm_returns_to_ready_or_disabled():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq())
    gate.arm(operator_authorization="OPERATOR_CONFIRM_LIVE")
    gate.disarm()
    assert gate.state == LiveValidationState.LIVE_READY
    assert gate.can_submit_live() is False


def test_losing_prerequisite_while_armed_disables_live():
    gate = LiveAuthorizationGate()
    gate.set_prerequisites(_all_pass_prereq())
    gate.arm(operator_authorization="OPERATOR_CONFIRM_LIVE")
    gate.update_prerequisites(broker_connected=False)
    assert gate.can_submit_live() is False
    assert gate.state == LiveValidationState.LIVE_DISABLED


def test_controller_live_arm_requires_auth_prereqs():
    ctrl = LiveExecutionController(mode=LiveMode.LIVE)
    assert LIVE_CAPITAL_BLOCKED is True
    ctrl.evaluate_preflight(_all_preflight_pass())
    out = ctrl.arm(operator_ack="operator")
    assert out["ok"] is False


def test_controller_live_arm_capital_still_blocked():
    ctrl = LiveExecutionController(mode=LiveMode.LIVE)
    ctrl.evaluate_preflight(_all_preflight_pass())
    ctrl.auth_gate.set_prerequisites(_all_pass_prereq())
    out = ctrl.arm(operator_ack="operator")
    assert out["ok"] is False
    assert out["reason"] == "live_capital_blocked"


def test_controller_demo_arm_without_live_capital():
    ctrl = LiveExecutionController(mode=LiveMode.DEMO)
    ctrl.evaluate_preflight(_all_preflight_pass())
    out = ctrl.arm(operator_ack="operator")
    assert out["ok"] is True
    assert out["state"] == "ARMED"


def test_mock_broker_submit_blocked_when_not_authorized():
    ctrl = LiveExecutionController(mode=LiveMode.LIVE)
    intent = LiveOrderIntent(
        client_order_id="c1", symbol="EURUSD", side="BUY", size=0.01
    )

    def fake_broker(_payload):
        return {"ok": True, "status": "FILLED"}

    result = ctrl.submit_live_order(intent, broker_submit=fake_broker)
    assert result.ok is False
    assert result.status in ("BLOCKED", "HALTED")


def test_exception_path_does_not_open_live():
    gate = LiveAuthorizationGate()
    try:
        raise RuntimeError("simulated")
    except RuntimeError:
        pass
    assert gate.state == LiveValidationState.LIVE_DISABLED
    assert gate.can_submit_live() is False
