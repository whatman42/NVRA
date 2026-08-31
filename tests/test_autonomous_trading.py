"""Autonomous lifecycle tests — no real LIVE broker orders."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from god.live.autonomous_policy import (
    AutonomousTradingPolicy,
    enable_autonomous_live,
    enable_autonomous_paper,
    load_policy,
    save_policy,
    FORBIDDEN_KEYS,
)
from god.live.autonomous_runtime import (
    run_autonomous_startup,
    evaluate_runtime_prechecks,
)
from god.live.authorization import LiveAuthorizationGate
from god.live.models import LiveValidationState
from god.mt5_runtime.safety_gate import LIVE_CAPITAL_BLOCKED, LiveCapitalGate
from scripts.nvrafx_entry import build_parser


def _ok_probes(**overrides):
    base = dict(
        license_valid=True,
        device_valid=True,
        credentials_valid=True,
        broker_connected=True,
        state_loaded=True,
        reconciliation_pass=True,
        risk_governor_ready=True,
        startup_ready=True,
        artifact_integrity=True,
        config_valid=True,
    )
    base.update(overrides)
    return lambda: base


def test_admin_configuration_enables_autonomous_live(tmp_path):
    path = tmp_path / "autonomous_trading_policy.json"
    pol = enable_autonomous_live(path)
    assert pol.autonomous_live is True
    assert pol.trading_mode == "LIVE"
    loaded = load_policy(path)
    assert loaded is not None
    assert loaded.autonomous_live is True


def test_live_authorization_persists_without_credentials(tmp_path):
    path = tmp_path / "autonomous_trading_policy.json"
    enable_autonomous_live(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    for k in FORBIDDEN_KEYS:
        assert k not in raw
    assert "password" not in raw
    assert "api_key" not in raw
    assert "session_token" not in raw


def test_live_resumes_after_restart(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(data_dir=tmp_path, precheck=_ok_probes())
    assert r.ok is True
    assert r.mode == "LIVE"
    assert r.state == "RUNNING"
    assert r.details.get("can_submit_live") is True


def test_restart_does_not_require_manual_arm(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(data_dir=tmp_path, precheck=_ok_probes())
    assert r.reason == "autonomous_live_resumed"


def test_restart_does_not_require_gui(tmp_path):
    enable_autonomous_paper(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(data_dir=tmp_path, precheck=_ok_probes())
    assert r.headless is True
    assert r.ok is True


def test_autostart_is_headless():
    p = build_parser()
    args = p.parse_args(["--autostart", "--headless"])
    assert args.autostart and args.headless
    from scripts import nvrafx_entry as entry
    assert hasattr(entry, "_run_headless_autostart")


def test_demo_autonomous_restart(tmp_path):
    pol = AutonomousTradingPolicy(
        trading_mode="DEMO", autonomous_live=False, autonomous_enabled=True
    )
    save_policy(pol, tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(data_dir=tmp_path, precheck=_ok_probes())
    assert r.ok and r.mode == "DEMO" and r.state == "RUNNING"


def test_paper_autonomous_restart(tmp_path):
    enable_autonomous_paper(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(data_dir=tmp_path, precheck=_ok_probes())
    assert r.ok and r.mode == "PAPER"


def test_live_missing_credentials_fails_closed(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(
        data_dir=tmp_path, precheck=_ok_probes(credentials_valid=False), max_recovery_attempts=0
    )
    assert r.ok is False
    assert r.safe_mode is True
    assert "credentials_valid" in r.details.get("missing", [])


def test_live_invalid_license_fails_closed(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(
        data_dir=tmp_path, precheck=_ok_probes(license_valid=False), max_recovery_attempts=0
    )
    assert r.safe_mode is True


def test_live_broker_failure_enters_safe_mode(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(
        data_dir=tmp_path, precheck=_ok_probes(broker_connected=False), max_recovery_attempts=0
    )
    assert r.safe_mode is True
    assert r.state == "SAFE_MODE"


def test_live_reconciliation_failure_blocks_orders(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(
        data_dir=tmp_path, precheck=_ok_probes(reconciliation_pass=False), max_recovery_attempts=0
    )
    assert r.ok is False


def test_live_risk_failure_blocks_orders(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    r = run_autonomous_startup(
        data_dir=tmp_path, precheck=_ok_probes(risk_governor_ready=False), max_recovery_attempts=0
    )
    assert r.ok is False


def test_recovery_is_autonomous(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        ok = calls["n"] >= 2
        return dict(
            license_valid=ok,
            device_valid=ok,
            credentials_valid=ok,
            broker_connected=ok,
            state_loaded=ok,
            reconciliation_pass=ok,
            risk_governor_ready=ok,
            startup_ready=ok,
            artifact_integrity=True,
            config_valid=True,
        )

    r = run_autonomous_startup(data_dir=tmp_path, precheck=flaky, max_recovery_attempts=3)
    assert r.ok is True
    assert calls["n"] >= 2


def test_gui_crash_does_not_stop_core():
    gate = LiveAuthorizationGate()
    gate.note_gui_fault()
    assert gate.state == LiveValidationState.LIVE_DISABLED


def test_corrupt_persistent_state_does_not_enable_live(tmp_path):
    path = tmp_path / "autonomous_trading_policy.json"
    path.write_text("{not-json", encoding="utf-8")
    r = run_autonomous_startup(data_dir=tmp_path, precheck=_ok_probes())
    assert r.mode == "PAPER"
    assert r.details.get("live") is False


def test_credentials_are_not_written_to_runtime_state(tmp_path):
    path = tmp_path / "autonomous_trading_policy.json"
    enable_autonomous_live(path)
    text = path.read_text(encoding="utf-8")
    assert "api_key" not in text
    assert "password" not in text


def test_persistent_state_permissions(tmp_path):
    path = tmp_path / "autonomous_trading_policy.json"
    enable_autonomous_paper(path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600 or os.name == "nt"


def test_no_auto_arm_bypass():
    g = LiveCapitalGate(blocked=True)
    assert g.allow_live_execution() is False
    assert LIVE_CAPITAL_BLOCKED is True


def test_no_live_order_before_all_preconditions(tmp_path):
    enable_autonomous_live(tmp_path / "autonomous_trading_policy.json")
    ok, _, missing = evaluate_runtime_prechecks(credentials_valid=False)
    assert ok is False
    assert "credentials_valid" in missing
    r = run_autonomous_startup(
        data_dir=tmp_path, precheck=_ok_probes(credentials_valid=False), max_recovery_attempts=0
    )
    assert r.ok is False


def test_ml_cannot_set_administrative_authorization():
    g = LiveCapitalGate(blocked=True)
    assert not hasattr(g, "authorize_from_ml")
    assert g.administrative_live_authorized is False
    assert g.allow_live_execution() is False
