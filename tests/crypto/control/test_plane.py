"""Control plane auth, emergency stop, cashout, risk isolation."""

from __future__ import annotations

from crypto.control import CommandResult, ControlPlane, PinAuthState
from crypto.risk.policy import RiskPolicy


def test_passive_ok() -> None:
    cp = ControlPlane()
    cp.authorize_chat("1")
    r = cp.dispatch("saldo", actor="tg:1", chat_id="1")
    assert r.result is CommandResult.OK


def test_unknown_command() -> None:
    cp = ControlPlane()
    cp.authorize_chat("1")
    r = cp.dispatch("hack_the_planet", actor="tg:1", chat_id="1")
    assert r.result is CommandResult.INVALID


def test_unauthorized_chat() -> None:
    cp = ControlPlane()
    r = cp.dispatch("saldo", actor="tg:9", chat_id="9")
    assert r.result is CommandResult.DENIED


def test_pin_and_emergency_stop() -> None:
    pin = PinAuthState()
    pin.set_pin("123456")
    cp = ControlPlane(pin_auth=pin)
    cp.authorize_chat("1")
    # without pin
    r = cp.dispatch("emergency_stop", actor="tg:1", chat_id="1")
    assert r.result is CommandResult.AUTH_REQUIRED
    # wrong pin
    r = cp.dispatch("emergency_stop", actor="tg:1", chat_id="1", pin="000000")
    assert r.result is CommandResult.DENIED
    # correct
    r = cp.dispatch("emergency_stop", actor="tg:1", chat_id="1", pin="123456")
    assert r.result is CommandResult.OK
    assert cp.runtime.emergency_stop is True
    # session allows second critical without pin
    r2 = cp.dispatch("set_mode_paper", actor="tg:1", chat_id="1")
    assert r2.result is CommandResult.OK


def test_pin_lockout() -> None:
    pin = PinAuthState()
    pin.set_pin("654321")
    cp = ControlPlane(pin_auth=pin)
    cp.authorize_chat("1")
    for _ in range(5):
        cp.dispatch("emergency_stop", actor="tg:1", chat_id="1", pin="111111")
    r = cp.dispatch("emergency_stop", actor="tg:1", chat_id="1", pin="654321")
    assert r.result in (CommandResult.LOCKED, CommandResult.DENIED)


def test_cashout_manual() -> None:
    pin = PinAuthState()
    pin.set_pin("123456")
    cp = ControlPlane(pin_auth=pin)
    cp.authorize_chat("1")
    r = cp.dispatch(
        "cashout",
        actor="tg:1",
        chat_id="1",
        pin="123456",
        params={"amount": 100.0, "available_balance": 500.0},
    )
    assert r.result is CommandResult.UNAVAILABLE
    assert "MANUAL" in r.message


def test_risk_policy_unchanged_by_emergency() -> None:
    policy = RiskPolicy(max_position_pct=7.0)
    cp = ControlPlane(risk_policy=policy)
    cp.authorize_chat("1")
    # no pin set → critical allowed without pin when has_pin is False
    fp_before = cp.risk_policy_fingerprint()
    cp.dispatch("emergency_stop", actor="tg:1", chat_id="1")
    assert cp.risk_policy_fingerprint() == fp_before
    assert cp.risk_policy.max_position_pct == 7.0
