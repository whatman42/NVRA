"""Local user registry — registration and credential verification."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from .identity import UserIdentity, IdentityError
from .password import hash_password, verify_password

from god.persist.secure_write import secure_write_json


@dataclass
class RegistrationResult:
    ok: bool
    identity: Optional[UserIdentity] = None
    reason: str = ""


class UserRegistry:
    """File-backed user store. No plaintext passwords."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._users: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._users = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._users = dict(data.get("users") or {})
        except (OSError, json.JSONDecodeError):
            self._users = {}

    def _save(self) -> None:
        payload = {"version": 1, "users": self._users}
        secure_write_json(self.path, payload)

    def register(
        self,
        username: str,
        password: str,
        *,
        display_name: Optional[str] = None,
    ) -> RegistrationResult:
        key = username.strip().lower()
        if not key or not password:
            return RegistrationResult(False, reason="username_and_password_required")
        if key in self._users:
            return RegistrationResult(False, reason="username_taken")
        try:
            identity = UserIdentity.create(username, display_name)
        except IdentityError as e:
            return RegistrationResult(False, reason=str(e))
        record = {
            "identity": identity.to_dict(),
            "password_hash": hash_password(password),
        }
        self._users[key] = record
        self._save()
        return RegistrationResult(True, identity=identity, reason="registered")

    def authenticate(self, username: str, password: str) -> Optional[UserIdentity]:
        key = username.strip().lower()
        rec = self._users.get(key)
        if not rec:
            return None
        if not verify_password(password, rec.get("password_hash", "")):
            return None
        try:
            return UserIdentity.from_dict(rec["identity"])
        except IdentityError:
            return None

    def get(self, username: str) -> Optional[UserIdentity]:
        rec = self._users.get(username.strip().lower())
        if not rec:
            return None
        try:
            return UserIdentity.from_dict(rec["identity"])
        except IdentityError:
            return None
