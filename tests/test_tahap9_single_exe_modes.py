"""Single NUNG.exe modes: Trial / Client / Root Admin — no username-based admin."""
from __future__ import annotations

from pathlib import Path

import pytest

from god.app import NungApplication, AppMode, Role
from god.auth.session import SessionError


def test_trial_mode_paper_only(tmp_path: Path):
    app = NungApplication(tmp_path / "data")
    r = app.start_trial()
    assert r["ok"] is True
    assert r["mode"] == "TRIAL"
    assert r["live_capital"] == "BLOCKED"
    assert "paper_trading" in r["capabilities"]
    assert "license_keygen" not in r["capabilities"]
    # trial cannot save client data
    assert app.save_state("x", tmp_path / "f.nung")["ok"] is False


def test_register_always_client(tmp_path: Path):
    app = NungApplication(tmp_path / "data")
    r = app.register_client("alice", "client-pass-99", "Alice")
    assert r["ok"] is True
    assert r["role"] == "CLIENT"
    login = app.login("alice", "client-pass-99")
    assert login["ok"] is True
    assert login["mode"] == "CLIENT"
    assert login["role"] == "CLIENT"


def test_root_admin_init_not_username_based(tmp_path: Path):
    app = NungApplication(tmp_path / "data")
    assert app.needs_root_admin() is True
    # insecure default rejected even if username is ops
    bad = app.initialize_root_admin("admin", "admin")
    assert bad["ok"] is False
    ok = app.initialize_root_admin("ops_root", "VeryStr0ng-Root-Pass!", "Ops")
    assert ok["ok"] is True
    assert "recovery_token" in ok
    assert ok["role"] == "ROOT_ADMIN"
    assert app.needs_root_admin() is False
    # second init blocked
    again = app.initialize_root_admin("other", "AnotherStr0ng-Pass!")
    assert again["ok"] is False


def test_admin_login_by_crypto_record_not_username(tmp_path: Path):
    app = NungApplication(tmp_path / "data")
    app.initialize_root_admin("finance_lead", "VeryStr0ng-Root-Pass!")
    # username happens to not be 'admin' — still admin via root record
    login = app.login("finance_lead", "VeryStr0ng-Root-Pass!")
    assert login["ok"] is True
    assert login["mode"] == "ADMIN"
    assert login["role"] == "ROOT_ADMIN"
    # plain client with username admin is still CLIENT if registered as client
    app.register_client("admin", "client-pass-99")
    clogin = app.login("admin", "client-pass-99")
    assert clogin["ok"] is True
    assert clogin["mode"] == "CLIENT"
    assert clogin["role"] == "CLIENT"


def test_admin_control_requires_admin_mode(tmp_path: Path):
    app = NungApplication(tmp_path / "data")
    app.initialize_root_admin("ops_root", "VeryStr0ng-Root-Pass!")
    app.register_client("bob", "client-pass-99")
    client_tok = app.login("bob", "client-pass-99")["token"]
    denied = app.admin_list_clients(client_tok)
    assert denied["ok"] is False
    admin_tok = app.login("ops_root", "VeryStr0ng-Root-Pass!")["token"]
    listed = app.admin_list_clients(admin_tok)
    assert listed["ok"] is True
    assert any(c["username"] == "bob" for c in listed["clients"])


def test_no_nung_keygen_exe_design():
    """Architectural invariant: KeyGen is admin function, not separate product binary."""
    from god.app import modes

    assert hasattr(modes.AppMode, "ADMIN")
    assert "license_keygen" in modes.ADMIN_CAPABILITIES
