"""Control plane: Ed25519, RBAC, fallback, gate, tenant isolation."""
from __future__ import annotations
import time
from pathlib import Path
import pytest
from god.control_plane import (
    ControlPlaneStore, FallbackStore, Forbidden, LicenseGate, LicenseKeyPair, Role,
    SignedFallbackState, admin_clients, client_portfolio, evaluate_offline, verify_license_payload,
)
from god.control_plane.ed25519_license import build_license_payload, license_expired, sign_license_payload
from god.control_plane.rbac import require_super_admin

def test_ed25519_roundtrip():
    kp = LicenseKeyPair.generate()
    payload = build_license_payload(username="u1", license_id="L1", issued_at="2026-01-01T00:00:00Z")
    sig = sign_license_payload(kp.private_key_pem, payload)
    assert verify_license_payload(kp.public_key_pem, payload, sig)
    payload2 = dict(payload); payload2["username"] = "x"
    assert not verify_license_payload(kp.public_key_pem, payload2, sig)

def test_unlimited_and_expired():
    assert not license_expired({"expires_at": None})
    assert license_expired({"expires_at": "2020-01-01T00:00:00Z"})

def test_issue_verify_revoke():
    store = ControlPlaneStore()
    admin = store.create_account("root", Role.SUPER_ADMIN)
    client = store.create_account("c1", Role.CLIENT)
    lic = store.issue_license(client.id, actor=admin.id)
    assert store.verify_license(lic.id)[0]
    store.revoke_license(lic.id, actor=admin.id)
    ok, reason = store.verify_license(lic.id)
    assert not ok and reason == "revoked"

def test_rbac_and_tenant():
    store = ControlPlaneStore()
    admin = store.create_account("root", Role.SUPER_ADMIN)
    a = store.create_account("a", Role.CLIENT)
    b = store.create_account("b", Role.CLIENT)
    assert len(admin_clients(store, admin.id)) == 2
    with pytest.raises(Forbidden):
        admin_clients(store, a.id)
    assert client_portfolio(store, a.id, requested_client_id=b.id)["client_id"] == a.id
    assert client_portfolio(store, admin.id, requested_client_id=b.id)["client_id"] == b.id

def test_fallback_valid_and_tamper(tmp_path: Path):
    kp = LicenseKeyPair.generate()
    path = tmp_path / "fb.json"
    fb = FallbackStore(path, public_pem=kp.public_key_pem, private_pem=kp.private_key_pem)
    st = SignedFallbackState(license_status="ACTIVE", account_status="ACTIVE", device_status="ACTIVE",
                             paper_only=True, last_sync_at=time.time())
    fb.sign_and_save(st)
    loaded, why = fb.load_and_verify()
    d = evaluate_offline(loaded, why)
    assert d.allowed and d.live_trading is False and d.risk_ceiling_raise is False
    path.write_text(path.read_text().replace("ACTIVE", "DISABLED", 1))
    _, why2 = fb.load_and_verify()
    assert why2 == "bad_signature"
    assert not evaluate_offline(None, why2).allowed

def test_clock_rollback_and_revoked_fallback():
    st = SignedFallbackState(license_status="ACTIVE", account_status="ACTIVE", device_status="ACTIVE",
                             paper_only=True, last_known_time=time.time() + 9999)
    assert evaluate_offline(st, "ok", now=time.time()).reason == "clock_rollback"
    st2 = SignedFallbackState(license_status="REVOKED", account_status="ACTIVE", device_status="ACTIVE", paper_only=True)
    assert evaluate_offline(st2, "ok").mode == "LICENSE_BLOCKED"

def test_gate_online_and_offline(tmp_path: Path):
    store = ControlPlaneStore()
    admin = store.create_account("root", Role.SUPER_ADMIN)
    c = store.create_account("c", Role.CLIENT)
    lic = store.issue_license(c.id, actor=admin.id)
    assert LicenseGate(store=store).check(license_id=lic.id).allowed
    fb = FallbackStore(tmp_path / "fb.json", public_pem=store.keypair.public_key_pem, private_pem=store.keypair.private_key_pem)
    fb.sign_and_save(SignedFallbackState(license_status="ACTIVE", account_status="ACTIVE", device_status="ACTIVE", paper_only=True, last_sync_at=time.time()))
    r = LicenseGate(store=store, fallback=fb).check(cloud_available=False)
    assert r.allowed and r.offline

def test_session_heartbeat():
    store = ControlPlaneStore()
    admin = store.create_account("root", Role.SUPER_ADMIN)
    c = store.create_account("c", Role.CLIENT)
    lic = store.issue_license(c.id, actor=admin.id)
    dev = store.register_device(c.id)
    sess, raw = store.create_session(c.id, dev.id)
    assert store.validate_session(sess.id, raw)[0]
    store.record_heartbeat(account_id=c.id, device_id=dev.id, license_id=lic.id, client_version="1", status="OK", state_hash="h")
    assert store.heartbeats
