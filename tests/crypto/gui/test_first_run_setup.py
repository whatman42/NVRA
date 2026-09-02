"""First-run wizard order, PAPER default, optional skips, secret hygiene, setup state."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from crypto.execution.models import ExecutionMode
from crypto.gui.first_run import FirstRunController
from crypto.gui.setup_state import load_setup_state, FirstRunSetupState
from crypto.gui.wizard import (
    OPTIONAL_STEPS,
    SUPPORTED_EXCHANGES,
    WIZARD_ORDER,
    WizardState,
    WizardStep,
)


def test_wizard_order_matches_spec():
    names = [s.name for s in WIZARD_ORDER]
    assert names[0] == "WELCOME"
    assert names[1] == "HARDWARE"
    assert names[2] == "OPERATOR"
    assert names[3] == "DATA"
    assert names[4] == "EXCHANGE"
    assert "TELEGRAM" in names
    assert "COMPUTE" in names
    assert "SECURITY" in names
    assert names[-2] == "VALIDATE"
    assert names[-1] == "DONE"


def test_default_mode_is_paper():
    w = WizardState()
    assert w.mode == ExecutionMode.PAPER
    assert w.summary()["execution_mode"] == "PAPER ONLY"


def test_optional_steps():
    assert WizardStep.TELEGRAM in OPTIONAL_STEPS
    assert WizardStep.COMPUTE in OPTIONAL_STEPS
    assert WizardStep.OPERATOR not in OPTIONAL_STEPS


def test_supported_exchanges():
    assert "binance" in SUPPORTED_EXCHANGES
    assert "mt5" in SUPPORTED_EXCHANGES


def test_advance_requires_operator(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.bootstrap_welcome()
    c.state.step = WizardStep.OPERATOR
    ok, reason = c.advance()
    assert not ok and "operator" in reason


def test_skip_telegram_and_compute(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.state.step = WizardStep.TELEGRAM
    c.state.set_telegram_token("should-clear-on-skip-path")
    ok, _ = c.skip_optional()
    assert ok
    assert c.state.telegram_skipped
    c.state.step = WizardStep.COMPUTE
    ok, _ = c.skip_optional()
    assert ok
    assert c.state.colab_enabled is False
    assert c.state.kaggle_enabled is False
    assert c.state.local_compute_enabled is True


def test_compute_defaults_cloud_disabled(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.configure_compute(colab_enabled=False, kaggle_enabled=False)
    assert c.state.colab_status == "DISABLED"
    assert c.state.kaggle_status == "DISABLED"
    assert c.state.local_compute_enabled is True


def test_secrets_cleared_by_take_secrets():
    w = WizardState()
    w.set_api_key("KEY")
    w.set_api_secret("SECRET")
    w.set_telegram_token("TOK")
    w.set_operator_password("PW")
    w.set_kaggle_token("KG")
    secrets = w.take_secrets()
    assert secrets["api_key"] == "KEY"
    assert not w.has_pending_secrets()
    assert "KEY" not in repr(w)


def test_security_review_paper_and_sanitize(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.state.mode = ExecutionMode.PAPER
    c.state.local_compute_enabled = True
    checks = c.run_security_review()
    assert checks and all(ch.passed for ch in checks)


def test_validation_paper_local(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.state.mode = ExecutionMode.PAPER
    c.state.exchange_id = "binance"
    c.state.data_dir = str(tmp_path)
    c.state.state_dir = str(tmp_path)
    assert c.run_validation() is True


def test_complete_persists_non_secret_state(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.bootstrap_welcome()
    c.apply_hardware()
    c.state.operator_username = "ops"
    c.state.exchange_id = "binance"
    c.state.mode = ExecutionMode.PAPER
    c.state.local_compute_enabled = True
    c.run_security_review()
    c.state.validation_ok = True
    setup = c.complete()
    assert setup.setup_completed
    raw = json.loads((tmp_path / "first_run_setup.json").read_text())
    for forbidden in ("password", "api_key", "api_secret", "private_key"):
        assert forbidden not in raw


def test_setup_state_rejects_secret_keys(tmp_path: Path):
    from crypto.gui.setup_state import _assert_no_secrets_in_payload

    with pytest.raises(ValueError):
        _assert_no_secrets_in_payload({"api_key": "x", "setup_completed": True})


def test_full_happy_path_to_done(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.bootstrap_welcome()
    c.apply_hardware()
    c.state.step = WizardStep.OPERATOR
    c.state.operator_username = "alice"
    c.state.set_operator_password("StrongPass1!")
    assert c.advance()[0]
    c.state.step = WizardStep.DATA
    assert c.advance()[0]
    c.state.step = WizardStep.EXCHANGE
    c.state.exchange_id = "binance"
    assert c.advance()[0]
    c.state.step = WizardStep.CREDENTIALS
    assert c.advance()[0]
    c.state.step = WizardStep.TELEGRAM
    assert c.skip_optional()[0]
    c.state.step = WizardStep.COMPUTE
    assert c.skip_optional()[0]
    c.state.step = WizardStep.SECURITY
    c.run_security_review()
    assert c.advance()[0]
    c.state.step = WizardStep.VALIDATE
    c.state.data_dir = str(tmp_path)
    c.state.state_dir = str(tmp_path)
    c.run_validation()
    assert c.state.validation_ok
    assert c.advance()[0]
    assert c.state.step == WizardStep.DONE
    assert c.state.summary()["execution_mode"] == "PAPER ONLY"


def test_colab_unavailable_status_not_connected(tmp_path: Path):
    c = FirstRunController(state_dir=tmp_path)
    c.configure_compute(colab_enabled=True, kaggle_enabled=False)
    assert c.state.colab_status != "CONNECTED"
