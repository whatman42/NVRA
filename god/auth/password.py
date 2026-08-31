"""Secure password hashing (PBKDF2-HMAC-SHA256). Never store plaintext."""
from __future__ import annotations

import hashlib
import hmac
import os
from typing import Tuple

_ITERATIONS = 200_000
_SALT_LEN = 16
_DK_LEN = 32


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return encoded string: iterations$salt_hex$dk_hex."""
    if not isinstance(password, str) or not password:
        raise ValueError("password must be non-empty str")
    if salt is None:
        salt = os.urandom(_SALT_LEN)
    if len(salt) < 8:
        raise ValueError("salt too short")
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=_DK_LEN)
    return f"{_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verify against encoded hash."""
    try:
        parts = encoded.split("$")
        if len(parts) != 3:
            return False
        iterations = int(parts[0])
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
    except (ValueError, TypeError):
        return False
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(dk, expected)
