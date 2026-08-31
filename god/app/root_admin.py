"""First-time Root Administrator initialization.

No default admin. No username-based admin. No hardcoded password.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from god.auth.password import hash_password, verify_password
from god.keygen.signing import SigningKeyPair, generate_ephemeral_keypair

from .modes import Role


@dataclass
class RootAdminRecord:
    admin_id: str
    username: str
    display_name: str
    role: str
    password_hash: str
    public_key_id: str
    # private material stored encrypted at rest as hex; never logged
    private_material_hex: str
    recovery_token_hash: str
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "admin_id": self.admin_id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "password_hash": self.password_hash,
            "public_key_id": self.public_key_id,
            "private_material_hex": self.private_material_hex,
            "recovery_token_hash": self.recovery_token_hash,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RootAdminRecord":
        return cls(
            admin_id=str(data["admin_id"]),
            username=str(data["username"]),
            display_name=str(data.get("display_name") or data["username"]),
            role=str(data.get("role") or Role.ROOT_ADMIN.value),
            password_hash=str(data["password_hash"]),
            public_key_id=str(data["public_key_id"]),
            private_material_hex=str(data["private_material_hex"]),
            recovery_token_hash=str(data["recovery_token_hash"]),
            created_at=str(data["created_at"]),
        )


class RootAdminStore:
    """Single root admin file. Created only via explicit initialization."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def exists(self) -> bool:
        return self.path.exists()

    def load(self) -> Optional[RootAdminRecord]:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return RootAdminRecord.from_dict(data)
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def initialize(
        self,
        username: str,
        password: str,
        *,
        display_name: str = "",
    ) -> Dict[str, Any]:
        """Create root admin once. Returns recovery_token ONCE (caller must display securely)."""
        if self.exists():
            return {"ok": False, "reason": "root_admin_already_exists"}
        if not username or not password or len(password) < 10:
            return {"ok": False, "reason": "username_and_strong_password_required"}
        # Reject trivial identities
        if username.strip().lower() in {"admin", "root", "master"} and password.lower() in {
            "admin",
            "password",
            "master",
            "root",
            "admin123",
        }:
            return {"ok": False, "reason": "insecure_default_rejected"}

        import uuid
        from datetime import datetime, timezone

        kp = generate_ephemeral_keypair()
        recovery_token = secrets.token_urlsafe(32)
        import hashlib

        recovery_hash = hashlib.sha256(recovery_token.encode()).hexdigest()
        record = RootAdminRecord(
            admin_id=str(uuid.uuid4()),
            username=username.strip(),
            display_name=(display_name or username).strip(),
            role=Role.ROOT_ADMIN.value,
            password_hash=hash_password(password),
            public_key_id=kp.public_id,
            private_material_hex=kp.private_material.hex(),
            recovery_token_hash=recovery_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record.to_dict(), indent=2), encoding="utf-8")
        try:
            tmp.chmod(0o600)
        except OSError:
            pass
        tmp.replace(self.path)
        return {
            "ok": True,
            "admin_id": record.admin_id,
            "public_key_id": record.public_key_id,
            "recovery_token": recovery_token,  # show once — never logged by caller ideally
            "role": Role.ROOT_ADMIN.value,
        }

    def authenticate(self, username: str, password: str) -> Optional[RootAdminRecord]:
        rec = self.load()
        if rec is None:
            return None
        if rec.username.strip().lower() != username.strip().lower():
            return None
        if not verify_password(password, rec.password_hash):
            return None
        if rec.role not in (Role.ROOT_ADMIN.value, Role.ADMIN.value):
            return None
        return rec

    def signing_keypair(self) -> Optional[SigningKeyPair]:
        rec = self.load()
        if rec is None:
            return None
        try:
            material = bytes.fromhex(rec.private_material_hex)
            return SigningKeyPair(private_material=material, public_id=rec.public_key_id)
        except ValueError:
            return None
