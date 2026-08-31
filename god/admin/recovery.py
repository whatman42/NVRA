"""Account recovery — one-time short-lived tokens. Admin never sees passwords."""
from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass
from typing import Dict, Optional

from god.auth.password import hash_password
from god.auth.registry import UserRegistry

from .audit import AuditLog


class RecoveryError(Exception):
    pass


@dataclass
class _TokenRecord:
    user_id: str
    token_hash: str
    expires_at: float
    used: bool = False


class RecoveryService:
    """In-memory recovery tokens (persist optional later). Never stores plaintext token."""

    def __init__(
        self,
        registry: UserRegistry,
        audit: AuditLog,
        *,
        ttl_seconds: int = 900,
    ):
        self.registry = registry
        self.audit = audit
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._tokens: Dict[str, _TokenRecord] = {}

    def request_password_reset(self, username: str, *, actor_id: str = "system") -> str:
        identity = self.registry.get(username)
        if identity is None:
            # Do not reveal whether user exists
            self.audit.record(
                actor_id=actor_id,
                target_id=username,
                action="PASSWORD_RESET_REQUESTED",
                result="UNKNOWN_USER",
            )
            raise RecoveryError("recovery_unavailable")
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        self._tokens[token_hash] = _TokenRecord(
            user_id=identity.user_id,
            token_hash=token_hash,
            expires_at=time.time() + self.ttl_seconds,
        )
        self.audit.record(
            actor_id=actor_id,
            target_id=identity.user_id,
            action="PASSWORD_RESET_REQUESTED",
            result="SUCCESS",
        )
        return token  # returned once to verified channel only

    def complete_password_reset(
        self,
        username: str,
        token: str,
        new_password: str,
        *,
        actor_id: str = "system",
    ) -> None:
        if not new_password or len(new_password) < 8:
            raise RecoveryError("password_too_weak")
        identity = self.registry.get(username)
        if identity is None:
            raise RecoveryError("recovery_unavailable")
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        rec = self._tokens.get(token_hash)
        if rec is None or rec.used or rec.user_id != identity.user_id:
            self.audit.record(
                actor_id=actor_id,
                target_id=identity.user_id,
                action="PASSWORD_RESET_COMPLETED",
                result="INVALID_TOKEN",
            )
            raise RecoveryError("invalid_token")
        if time.time() >= rec.expires_at:
            self.audit.record(
                actor_id=actor_id,
                target_id=identity.user_id,
                action="PASSWORD_RESET_COMPLETED",
                result="EXPIRED",
            )
            raise RecoveryError("token_expired")
        # Update password in registry store
        key = username.strip().lower()
        users = self.registry._users  # intentional internal update
        if key not in users:
            raise RecoveryError("recovery_unavailable")
        users[key]["password_hash"] = hash_password(new_password)
        self.registry._save()
        rec.used = True
        self.audit.record(
            actor_id=actor_id,
            target_id=identity.user_id,
            action="PASSWORD_RESET_COMPLETED",
            result="SUCCESS",
        )
