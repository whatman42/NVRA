"""TAHAP 9 — admin, license lifecycle, recovery, audit, encrypted chat."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from god.admin import AdminApplication, LicenseStatus, RecoveryError
from god.comms import ChatService, ChatError
from god.auth import UserRegistry
from god.auth.identity import UserIdentity
from god.keygen.signing import generate_ephemeral_keypair
from god.admin.license_store import LicenseStore
from god.admin.device_store import DeviceStore
from god.admin.audit import AuditLog


def test_admin_reject_insecure_default(tmp_path: Path):
    app = AdminApplication(tmp_path / "adm")
    bad = app.register_admin("admin", "admin")
    assert bad["ok"] is False
    ok = app.register_admin("ops_lead", "Str0ng-Adm1n-Pass!")
    assert ok["ok"] is True
    login = app.login("ops_lead", "Str0ng-Adm1n-Pass!")
    assert login["ok"] is True


def test_license_create_revoke_restore_expiry(tmp_path: Path):
    app = AdminApplication(tmp_path / "adm")
    app.register_admin("ops", "Str0ng-Adm1n-Pass!")
    token = app.login("ops", "Str0ng-Adm1n-Pass!")["token"]
    # client
    app.clients.register("trader1", "client-pass-99")
    client = app.clients.get("trader1")
    assert client is not None
    lic = app.create_license(
        token, user_id=client.user_id, username="trader1", expires_in_days=None
    )
    assert lic["ok"] is True
    assert lic["license"]["status"] == "ACTIVE"
    lid = lic["license"]["license_id"]
    assert app.licenses.trading_allowed_for_user(client.user_id) is True
    rev = app.revoke_license(token, lid)
    assert rev["ok"] is True
    assert rev["license"]["status"] == "REVOKED"
    assert app.licenses.trading_allowed_for_user(client.user_id) is False
    res = app.restore_license(token, lid)
    assert res["ok"] is True
    assert app.licenses.trading_allowed_for_user(client.user_id) is True


def test_license_expiry_blocks_trading(tmp_path: Path):
    kp = generate_ephemeral_keypair()
    store = LicenseStore(tmp_path / "lic.json", kp)
    rec = store.create(user_id="u1", username="u1", expires_in_days=0)
    # force expires_at in the past
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    store._licenses[rec.license_id]["expires_at"] = past
    store._licenses[rec.license_id]["status"] = "ACTIVE"
    store._save()
    store.refresh_expiry_status(rec.license_id)
    updated = store.get(rec.license_id)
    assert updated is not None
    assert updated.status == LicenseStatus.EXPIRED
    assert store.trading_allowed_for_user("u1") is False


def test_device_revoke(tmp_path: Path):
    store = DeviceStore(tmp_path / "dev.json")
    d = store.register(user_id="u1", label="PC-A", os_name="Windows")
    assert store.is_allowed(d.device_id, "u1")
    store.revoke(d.device_id)
    assert store.is_allowed(d.device_id, "u1") is False


def test_recovery_token_one_time(tmp_path: Path):
    app = AdminApplication(tmp_path / "adm")
    app.clients.register("recuser", "old-password-1")
    token = app.recovery.request_password_reset("recuser")
    app.recovery.complete_password_reset("recuser", token, "new-password-99")
    assert app.clients.authenticate("recuser", "new-password-99") is not None
    assert app.clients.authenticate("recuser", "old-password-1") is None
    with pytest.raises(RecoveryError):
        app.recovery.complete_password_reset("recuser", token, "another-pass-99")


def test_audit_never_contains_password(tmp_path: Path):
    log = AuditLog(tmp_path / "audit.json")
    log.record(
        actor_id="a",
        target_id="b",
        action="USER_LOGIN",
        result="SUCCESS",
        details={"password": "secret", "note": "ok"},
    )
    events = log.list_events()
    assert len(events) == 1
    assert "password" not in events[0]["details"]
    assert events[0]["details"].get("note") == "ok"


def test_encrypted_chat_roundtrip(tmp_path: Path):
    chat = ChatService(tmp_path / "chat.json")
    msg = chat.send(sender_id="admin1", recipient_id="client1", plaintext="Hello support")
    inbox = chat.inbox("client1")
    assert len(inbox) == 1
    plain = chat.decrypt(inbox[0])
    assert plain == "Hello support"
    # ciphertext not equal plaintext on disk
    raw = (tmp_path / "chat.json").read_text(encoding="utf-8")
    assert "Hello support" not in raw


def test_chat_block(tmp_path: Path):
    chat = ChatService(tmp_path / "chat.json")
    chat.block_user("spammer")
    with pytest.raises(ChatError):
        chat.send(sender_id="spammer", recipient_id="victim", plaintext="hi")


def test_admin_list_and_chat(tmp_path: Path):
    app = AdminApplication(tmp_path / "adm")
    app.register_admin("ops", "Str0ng-Adm1n-Pass!")
    token = app.login("ops", "Str0ng-Adm1n-Pass!")["token"]
    app.clients.register("c1", "client-pass-99", display_name="Client One")
    client = app.clients.get("c1")
    assert client is not None
    listed = app.list_clients(token)
    assert listed["ok"] is True
    assert any(c["username"] == "c1" for c in listed["clients"])
    sent = app.chat_to_client(token, client.user_id, "Need help?")
    assert sent["ok"] is True
    events = app.audit_log(token)["events"]
    actions = {e["action"] for e in events}
    assert "MESSAGE_SENT" in actions
