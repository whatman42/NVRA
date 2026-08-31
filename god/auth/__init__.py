"""TAHAP 8 — Authentication, registration, and session management.

Fail-closed. Does not grant LIVE capital privileges.
"""
from __future__ import annotations

from .identity import UserIdentity, IdentityError
from .password import hash_password, verify_password
from .registry import UserRegistry, RegistrationResult
from .session import Session, SessionStore, SessionError

__all__ = [
    "UserIdentity",
    "IdentityError",
    "hash_password",
    "verify_password",
    "UserRegistry",
    "RegistrationResult",
    "Session",
    "SessionStore",
    "SessionError",
]
