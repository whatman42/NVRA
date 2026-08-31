"""Authenticated session store — no broker privileges implied."""
from __future__ import annotations

import secrets
import time
from dataclasses import dataclass, field
from typing import Dict, Optional

from .identity import UserIdentity


class SessionError(Exception):
    pass


@dataclass
class Session:
    token: str
    identity: UserIdentity
    created_at: float
    expires_at: float
    authenticated: bool = True

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at


class SessionStore:
    """In-memory sessions with optional TTL. Fail-closed on expiry."""

    def __init__(self, *, ttl_seconds: int = 86400):
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._sessions: Dict[str, Session] = {}

    def create(self, identity: UserIdentity) -> Session:
        token = secrets.token_urlsafe(32)
        now = time.time()
        session = Session(
            token=token,
            identity=identity,
            created_at=now,
            expires_at=now + self.ttl_seconds,
        )
        self._sessions[token] = session
        return session

    def get(self, token: str) -> Optional[Session]:
        session = self._sessions.get(token)
        if session is None:
            return None
        if session.expired:
            self._sessions.pop(token, None)
            return None
        return session

    def require(self, token: str) -> Session:
        session = self.get(token)
        if session is None:
            raise SessionError("invalid_or_expired_session")
        return session

    def revoke(self, token: str) -> None:
        self._sessions.pop(token, None)
