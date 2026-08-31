"""TAHAP 8 — auth, license, save/load, wrong-user block, live gate."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from god.auth import UserRegistry, SessionStore, hash_password, verify_password
from god.auth.identity import UserIdentity
from god.keygen import generate_ephemeral_keypair, issue_license, verify_license, LicensePayload
from god.keygen.license import LicenseError
from god.persist import save_bundle, load_bundle, verify_bundle_owner, ExportError
from god.mt5_runtime import detect_mt5, LiveCapitalGate, LIVE_CAPITAL_BLOCKED, MT5ConnectionState
from god.app import NungApplication


def test_password_hash_roundtrip():
    enc = hash_password("s3cret-pass")
    assert verify_password("s3cret-pass", enc)
    assert not verify_password("wrong", enc)
    assert "$" in enc


def test_register_login_session(tmp_path: Path):
    reg = UserRegistry(tmp_path / "users.json")
    r = reg.register("alice", "pw-alice", display_name="Alice")
    assert r.ok and r.identity is not None
    assert reg.authenticate("alice", "pw-alice") is not None
    assert reg.authenticate("alice", "bad") is None
    store = SessionStore(ttl_seconds=3600)
    sess = store.create(r.identity)
    assert store.get(sess.token) is not None
    store.revoke(sess.token)
    assert store.get(sess.token) is None


def test_license_bind_and_verify():
    identity = UserIdentity.create("bob", "Bob")
    kp = generate_ephemeral_keypair()
    payload = LicensePayload(
        user_id=identity.user_id,
        username=identity.username,
        public_binding=identity.public_binding,
        issued_at=identity.created_at,
    )
    doc = issue_license(payload, kp)
    verified = verify_license(doc, kp, expected_user_id=identity.user_id)
    assert verified.user_id == identity.user_id
    with pytest.raises(LicenseError):
        verify_license(doc, kp, expected_user_id="other-user")


def test_save_load_wrong_user_blocked(tmp_path: Path):
    a = UserIdentity.create("owner")
    b = UserIdentity.create("intruder")
    path = tmp_path / "state.nung"
    save_bundle(path, a, model_metadata={"version": "1.0"})
    bundle = load_bundle(path)
    verify_bundle_owner(bundle, a)
    with pytest.raises(ExportError, match="wrong_user"):
        verify_bundle_owner(bundle, b)


def test_tampered_bundle_checksum(tmp_path: Path):
    identity = UserIdentity.create("carol")
    path = tmp_path / "t.nung"
    save_bundle(path, identity, checkpoint={"cycle": 1})
    data = json.loads(path.read_text(encoding="utf-8"))
    data["checkpoint"] = {"cycle": 999}
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ExportError, match="checksum"):
        load_bundle(path)


def test_mt5_detect_no_crash():
    result = detect_mt5()
    assert result.snapshot.state in {
        MT5ConnectionState.MT5_NOT_FOUND,
        MT5ConnectionState.MT5_DISCONNECTED,
    }
    assert isinstance(result.found, bool)


def test_live_capital_blocked_by_default():
    assert LIVE_CAPITAL_BLOCKED is True
    gate = LiveCapitalGate()
    assert gate.allow_live_execution() is False
    assert gate.allow_live_execution(unlock_token="anything") is False
    gate.assert_no_live_orders()
    assert gate.broker_orders_submitted == 0


def test_nung_app_register_login_save_load(tmp_path: Path):
    app = NungApplication(tmp_path / "data")
    reg = app.register("dana", "pw-dana", display_name="Dana")
    assert reg["ok"] is True
    login = app.login("dana", "pw-dana")
    assert login["ok"] is True
    token = login["token"]
    start = app.start(token)
    assert start["ok"] is True
    assert start["live_capital"] == "BLOCKED"
    assert start["broker_orders_submitted"] == 0
    path = tmp_path / "export.nung"
    assert app.save_state(token, path, model_metadata={"m": 1})["ok"] is True
    assert app.load_state(token, path)["ok"] is True
    # wrong user cannot load
    app.register("eve", "pw-eve")
    login2 = app.login("eve", "pw-eve")
    bad = app.load_state(login2["token"], path)
    assert bad["ok"] is False
    assert "wrong_user" in bad["reason"] or "blocked" in bad["reason"]
    stop = app.stop(token)
    assert stop["ok"] is True
    assert stop["broker_orders_submitted"] == 0
    dash = app.dashboard()
    assert dash["live_capital"] == "BLOCKED"
