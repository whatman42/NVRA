"""Administrator account registry — secure password hash, no defaults."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional

from god.auth.password import hash_password, verify_password

from .models import AdminIdentity, AdminStatus, utc_now


def _secure_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
        fd = -1
    finally:
        if fd != -1:
            os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


class AdminRegistry:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._admins: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self._admins = {}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._admins = dict(data.get("admins") or {})
        except (OSError, json.JSONDecodeError):
            self._admins = {}

    def _save(self) -> None:
        payload = {"version": 1, "admins": self._admins}
        _secure_write(self.path, json.dumps(payload, indent=2))

    def register(self, username: str, password: str, display_name: str = "") -> dict:
        key = username.strip().lower()
        if not key or not password:
            return {"ok": False, "reason": "username_and_password_required"}
        if key in self._admins:
            return {"ok": False, "reason": "username_taken"}
        # Reject trivial defaults
        if key in {"admin", "master", "root"} and password.lower() in {
            "admin",
            "master",
            "password",
            "root",
            "admin123",
        }:
            return {"ok": False, "reason": "insecure_default_rejected"}
        identity = AdminIdentity.create(username, display_name or None)
        self._admins[key] = {
            "identity": identity.to_dict(),
            "password_hash": hash_password(password),
        }
        self._save()
        return {"ok": True, "admin_id": identity.admin_id}

    def authenticate(self, username: str, password: str) -> Optional[AdminIdentity]:
        key = username.strip().lower()
        rec = self._admins.get(key)
        if not rec:
            return None
        if not verify_password(password, rec.get("password_hash", "")):
            return None
        identity = AdminIdentity.from_dict(rec["identity"])
        if identity.status != AdminStatus.ADMIN_ACTIVE:
            return None
        return identity
