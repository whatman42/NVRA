"""PIN-based secondary authentication for critical Telegram/GUI commands.

Never stores plaintext PIN. Never logs PIN.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from dataclasses import dataclass, field


def _hash_pin(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, 120_000)


@dataclass
class PinAuthConfig:
    max_failures: int = 5
    lockout_seconds: float = 300.0
    session_timeout_seconds: float = 300.0


@dataclass
class PinAuthState:
    salt: bytes = field(default_factory=lambda: os.urandom(16))
    verifier: bytes | None = None
    failures: int = 0
    locked_until_mono: float = 0.0
    session_ok_until_mono: float = 0.0

    def set_pin(self, pin: str) -> None:
        if not (pin.isdigit() and len(pin) == 6):
            raise ValueError("PIN must be exactly 6 digits")
        self.salt = os.urandom(16)
        self.verifier = _hash_pin(pin, self.salt)
        self.failures = 0
        self.locked_until_mono = 0.0

    def has_pin(self) -> bool:
        return self.verifier is not None

    def verify(
        self,
        pin: str,
        *,
        mono: float | None = None,
        config: PinAuthConfig | None = None,
    ) -> bool:
        cfg = config or PinAuthConfig()
        now = mono if mono is not None else time.monotonic()
        if now < self.locked_until_mono:
            return False
        if self.verifier is None:
            return False
        if not (pin.isdigit() and len(pin) == 6):
            self._fail(now, cfg)
            return False
        candidate = _hash_pin(pin, self.salt)
        ok = hmac.compare_digest(candidate, self.verifier)
        if ok:
            self.failures = 0
            self.session_ok_until_mono = now + cfg.session_timeout_seconds
            return True
        self._fail(now, cfg)
        return False

    def _fail(self, now: float, cfg: PinAuthConfig) -> None:
        self.failures += 1
        if self.failures >= cfg.max_failures:
            self.locked_until_mono = now + cfg.lockout_seconds
            self.failures = 0

    def session_valid(self, *, mono: float | None = None) -> bool:
        now = mono if mono is not None else time.monotonic()
        return now < self.session_ok_until_mono

    def revoke_session(self) -> None:
        self.session_ok_until_mono = 0.0

    def export_verifier(self) -> tuple[bytes, bytes] | None:
        """Return (salt, verifier) for secure persistence — never plaintext."""
        if self.verifier is None:
            return None
        return self.salt, self.verifier

    def import_verifier(self, salt: bytes, verifier: bytes) -> None:
        self.salt = salt
        self.verifier = verifier


def generate_session_token() -> str:
    return secrets.token_hex(16)
