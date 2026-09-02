"""In-process control-plane store (Postgres-ready). No secrets stored."""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Optional

from .ed25519_license import (
    LicenseKeyPair, build_license_payload, license_expired,
    sign_license_payload, verify_license_payload,
)
from .models import Account, AuditEvent, Device, Heartbeat, License, Session, new_id
from .roles import AccountStatus, DeviceStatus, LicenseStatus, Role


class ControlPlaneStore:
    def __init__(self, *, keypair: Optional[LicenseKeyPair] = None) -> None:
        self.keypair = keypair or LicenseKeyPair.generate()
        self.accounts: dict[str, Account] = {}
        self.licenses: dict[str, License] = {}
        self.devices: dict[str, Device] = {}
        self.sessions: dict[str, Session] = {}
        self.heartbeats: list[Heartbeat] = []
        self.audit: list[AuditEvent] = []
        self._by_username: dict[str, str] = {}

    def audit_log(self, actor: str, action: str, target: str, result: str, **details: object) -> AuditEvent:
        ev = AuditEvent(id=new_id(), actor=actor, action=action, target=target, result=result,
                        details={k: str(v) for k, v in details.items()})
        self.audit.append(ev)
        return ev

    def create_account(self, username: str, role: Role, *, actor: str = "system") -> Account:
        if username.lower() in self._by_username:
            raise ValueError("username_taken")
        acc = Account(id=new_id(), username=username, role=role)
        self.accounts[acc.id] = acc
        self._by_username[username.lower()] = acc.id
        self.audit_log(actor, "ACCOUNT_CREATED", acc.id, "ok", username=username, role=role.value)
        return acc

    def issue_license(self, account_id: str, *, expires_at: Optional[str] = None, actor: str = "system") -> License:
        acc = self.accounts[account_id]
        if acc.status != AccountStatus.ACTIVE:
            raise PermissionError("account_not_active")
        issued = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        lid = new_id()
        payload = build_license_payload(username=acc.username, license_id=lid, issued_at=issued, expires_at=expires_at)
        sig = sign_license_payload(self.keypair.private_key_pem, payload)
        lic = License(id=lid, account_id=account_id, username=acc.username, status=LicenseStatus.ACTIVE,
                      issued_at=issued, expires_at=expires_at, signature=sig, payload=payload)
        self.licenses[lid] = lic
        self.audit_log(actor, "LICENSE_CREATED", lid, "ok", account_id=account_id)
        return lic

    def verify_license(self, license_id: str) -> tuple[bool, str]:
        lic = self.licenses.get(license_id)
        if not lic:
            return False, "not_found"
        if lic.status == LicenseStatus.REVOKED:
            return False, "revoked"
        if lic.status == LicenseStatus.DISABLED:
            return False, "disabled"
        if not verify_license_payload(self.keypair.public_key_pem, lic.payload, lic.signature):
            return False, "bad_signature"
        if license_expired(lic.payload):
            lic.status = LicenseStatus.EXPIRED
            return False, "expired"
        if lic.payload.get("product") != "NVRA":
            return False, "wrong_product"
        return True, "ok"

    def revoke_license(self, license_id: str, *, actor: str) -> License:
        lic = self.licenses[license_id]
        lic.status = LicenseStatus.REVOKED
        self.audit_log(actor, "LICENSE_REVOKED", license_id, "ok")
        return lic

    def register_device(self, account_id: str, *, device_id: Optional[str] = None,
                       client_version: str = "", os_name: str = "", hostname: str = "",
                       actor: str = "system") -> Device:
        did = device_id or new_id()
        dev = Device(id=did, account_id=account_id, client_version=client_version, os_name=os_name, hostname=hostname)
        self.devices[did] = dev
        self.audit_log(actor, "DEVICE_REGISTERED", did, "ok", account_id=account_id)
        return dev

    def disable_device(self, device_id: str, *, actor: str) -> Device:
        dev = self.devices[device_id]
        dev.status = DeviceStatus.DISABLED
        self.audit_log(actor, "DEVICE_DISABLED", device_id, "ok")
        return dev

    def revoke_device(self, device_id: str, *, actor: str) -> Device:
        dev = self.devices[device_id]
        dev.status = DeviceStatus.REVOKED
        self.audit_log(actor, "DEVICE_REVOKED", device_id, "ok")
        return dev

    def create_session(self, account_id: str, device_id: str, *, ttl_sec: int = 86400) -> tuple[Session, str]:
        raw = secrets.token_urlsafe(32)
        th = hashlib.sha256(raw.encode()).hexdigest()
        sess = Session(id=new_id(), account_id=account_id, device_id=device_id, token_hash=th,
                       expires_at=time.time() + ttl_sec)
        self.sessions[sess.id] = sess
        self.audit_log(account_id, "SESSION_CREATED", sess.id, "ok")
        return sess, raw

    def validate_session(self, session_id: str, raw_token: str) -> tuple[bool, str]:
        sess = self.sessions.get(session_id)
        if not sess:
            return False, "not_found"
        if sess.revoked:
            return False, "revoked"
        if time.time() > sess.expires_at:
            return False, "expired"
        if hashlib.sha256(raw_token.encode()).hexdigest() != sess.token_hash:
            return False, "bad_token"
        return True, "ok"

    def revoke_session(self, session_id: str, *, actor: str) -> None:
        self.sessions[session_id].revoked = True
        self.audit_log(actor, "SESSION_REVOKED", session_id, "ok")

    def record_heartbeat(self, *, account_id: str, device_id: str, license_id: str,
                         client_version: str, status: str, state_hash: str,
                         runtime_status: str = "PAPER", safe_mode: bool = False) -> Heartbeat:
        hb = Heartbeat(
            id=new_id(), account_id=account_id, device_id=device_id, license_id=license_id,
            client_version=client_version[:64], timestamp=time.time(), status=status[:64],
            state_hash=state_hash[:128], runtime_status=runtime_status[:32], safe_mode=safe_mode,
        )
        self.heartbeats.append(hb)
        if device_id in self.devices:
            self.devices[device_id].last_seen = hb.timestamp
        self.audit_log(account_id, "HEARTBEAT_RECEIVED", device_id, "ok")
        return hb

    def list_clients(self) -> list[Account]:
        return [a for a in self.accounts.values() if a.role == Role.CLIENT]

    def public_key_pem(self) -> bytes:
        return self.keypair.public_key_pem
