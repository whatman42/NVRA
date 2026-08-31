"""Administrator application orchestrator (NUNG-KeyGen). No trading."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from god.auth import UserRegistry, SessionStore
from god.auth.session import SessionError
from god.keygen.signing import generate_ephemeral_keypair
from god.comms import ChatService

from .admin_registry import AdminRegistry
from .audit import AuditLog
from .device_store import DeviceStore
from .license_store import LicenseStore
from .models import LicenseStatus
from .recovery import RecoveryService, RecoveryError


class AdminApplication:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.admins = AdminRegistry(self.data_dir / "admins.json")
        self.clients = UserRegistry(self.data_dir / "clients.json")
        self.sessions = SessionStore()
        self.audit = AuditLog(self.data_dir / "audit.json")
        self.keypair = generate_ephemeral_keypair()
        self.licenses = LicenseStore(self.data_dir / "licenses.json", self.keypair)
        self.devices = DeviceStore(self.data_dir / "devices.json")
        self.recovery = RecoveryService(self.clients, self.audit)
        self.chat = ChatService(self.data_dir / "admin_chat.json")

    def register_admin(self, username: str, password: str, display_name: str = "") -> Dict[str, Any]:
        result = self.admins.register(username, password, display_name)
        if result.get("ok"):
            self.audit.record(
                actor_id=result["admin_id"],
                target_id=result["admin_id"],
                action="ADMIN_REGISTERED",
                result="SUCCESS",
            )
        return result

    def login(self, username: str, password: str) -> Dict[str, Any]:
        identity = self.admins.authenticate(username, password)
        if identity is None:
            self.audit.record(
                actor_id=username,
                target_id=username,
                action="ADMIN_LOGIN",
                result="FAILED",
            )
            return {"ok": False, "reason": "invalid_credentials"}
        session = self.sessions.create(
            # reuse UserIdentity-shaped session via minimal adapter
            __import__("god.auth.identity", fromlist=["UserIdentity"]).UserIdentity(
                user_id=identity.admin_id,
                username=identity.username,
                display_name=identity.display_name,
                created_at=identity.created_at,
                public_binding=identity.admin_id,
            )
        )
        self.audit.record(
            actor_id=identity.admin_id,
            target_id=identity.admin_id,
            action="ADMIN_LOGIN",
            result="SUCCESS",
        )
        return {"ok": True, "token": session.token, "admin_id": identity.admin_id}

    def _require(self, token: str):
        return self.sessions.require(token)

    def create_license(
        self,
        token: str,
        *,
        user_id: str,
        username: str,
        expires_in_days: Optional[int] = None,
    ) -> Dict[str, Any]:
        try:
            admin = self._require(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        rec = self.licenses.create(
            user_id=user_id, username=username, expires_in_days=expires_in_days
        )
        self.audit.record(
            actor_id=admin.identity.user_id,
            target_id=user_id,
            action="LICENSE_CREATED",
            result="SUCCESS",
            details={"license_id": rec.license_id, "expires_at": rec.expires_at},
        )
        return {"ok": True, "license": rec.to_dict()}

    def revoke_license(self, token: str, license_id: str) -> Dict[str, Any]:
        try:
            admin = self._require(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        rec = self.licenses.revoke(license_id)
        if rec is None:
            return {"ok": False, "reason": "not_found"}
        self.audit.record(
            actor_id=admin.identity.user_id,
            target_id=rec.user_id,
            action="LICENSE_REVOKED",
            result="SUCCESS",
            details={"license_id": license_id},
        )
        return {"ok": True, "license": rec.to_dict()}

    def restore_license(self, token: str, license_id: str) -> Dict[str, Any]:
        try:
            admin = self._require(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        rec = self.licenses.restore(license_id)
        if rec is None:
            return {"ok": False, "reason": "not_found"}
        self.audit.record(
            actor_id=admin.identity.user_id,
            target_id=rec.user_id,
            action="LICENSE_RESTORED",
            result="SUCCESS",
            details={"license_id": license_id, "status": rec.status.value},
        )
        return {"ok": True, "license": rec.to_dict()}

    def list_clients(self, token: str) -> Dict[str, Any]:
        try:
            self._require(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        clients = []
        for key, rec in self.clients._users.items():
            ident = rec.get("identity") or {}
            uid = ident.get("user_id", "")
            trading = self.licenses.trading_allowed_for_user(uid)
            clients.append(
                {
                    "username": ident.get("username"),
                    "user_id": uid,
                    "trading_allowed": trading,
                    "devices": [d.to_dict() for d in self.devices.for_user(uid)],
                }
            )
        return {"ok": True, "clients": clients}

    def audit_log(self, token: str, *, limit: int = 50) -> Dict[str, Any]:
        try:
            self._require(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        return {"ok": True, "events": self.audit.list_events(limit=limit)}

    def chat_to_client(self, token: str, client_user_id: str, text: str) -> Dict[str, Any]:
        try:
            admin = self._require(token)
        except SessionError as e:
            return {"ok": False, "reason": str(e)}
        try:
            msg = self.chat.send(
                sender_id=admin.identity.user_id,
                recipient_id=client_user_id,
                plaintext=text,
            )
            self.audit.record(
                actor_id=admin.identity.user_id,
                target_id=client_user_id,
                action="MESSAGE_SENT",
                result="SUCCESS",
                details={"message_id": msg.message_id},
            )
            return {"ok": True, "message_id": msg.message_id}
        except Exception as e:
            return {"ok": False, "reason": str(e)}
