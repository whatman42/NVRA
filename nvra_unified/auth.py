"""Local first-run authentication and credential enrollment.

Security:
- No default username/password.
- Passwords stored only as PBKDF2-HMAC-SHA256 verifiers (never plaintext).
- First-run enrollment is a one-shot offline fallback (O_EXCL).
- Login failures return explicit reasons without leaking secrets.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

REGISTRATION_SECRET_ENV = "NVRA_REGISTRATION_SECRET"
_AUTH_FILE_NAME = "auth_verifier.json"
_PBKDF2_ITERATIONS = 200_000


class AuthReason(str, Enum):
    OK = "ok"
    EMPTY_CREDENTIALS = "empty_credentials"
    ENROLLMENT_REQUIRED = "enrollment_required"
    ALREADY_ENROLLED = "already_enrolled"
    ACCOUNT_NOT_FOUND = "account_not_found"
    WRONG_PASSWORD = "wrong_password"
    CORRUPT_AUTH_STORE = "corrupt_auth_store"
    WRITE_FAILED = "write_failed"
    USERNAME_INVALID = "username_invalid"
    PASSWORD_TOO_SHORT = "password_too_short"


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    reason: AuthReason
    message: str = ""

    def to_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "reason": self.reason.value, "message": self.message}


_REASON_MESSAGES = {
    AuthReason.OK: "Authenticated.",
    AuthReason.EMPTY_CREDENTIALS: "Username and password are required.",
    AuthReason.ENROLLMENT_REQUIRED: (
        "No local operator is enrolled. Use Create Account (first-run enrollment) first."
    ),
    AuthReason.ALREADY_ENROLLED: (
        "A local operator account already exists. Use Login, or reset auth store offline if intentional."
    ),
    AuthReason.ACCOUNT_NOT_FOUND: "Account not found or credentials invalid.",
    AuthReason.WRONG_PASSWORD: "Account not found or credentials invalid.",
    AuthReason.CORRUPT_AUTH_STORE: "Local auth store is corrupt. Contact operator / re-enroll offline.",
    AuthReason.WRITE_FAILED: "Could not write auth store (permissions or disk).",
    AuthReason.USERNAME_INVALID: "Username must be 3–64 characters (letters, digits, _.-).",
    AuthReason.PASSWORD_TOO_SHORT: "Password must be at least 8 characters.",
}


def user_data_dir() -> Path:
    root = os.environ.get("NVRA_HOME")
    if root:
        return Path(root)
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "NVRA"
    return Path.home() / ".nvra"


def _auth_path() -> Path:
    return user_data_dir() / _AUTH_FILE_NAME


def enrollment_required() -> bool:
    return not _auth_path().is_file()


def _password_verifier(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"{_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _validate_username(username: str) -> AuthReason | None:
    key = username.strip()
    if len(key) < 3 or len(key) > 64:
        return AuthReason.USERNAME_INVALID
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    if any(c not in allowed for c in key):
        return AuthReason.USERNAME_INVALID
    return None


def _validate_password(password: str) -> AuthReason | None:
    if not password or len(password) < 8:
        return AuthReason.PASSWORD_TOO_SHORT
    return None


def enroll_first_user(username: str, password: str) -> bool:
    """Create the first local operator credential; never overwrites enrollment."""
    return create_account(username, password).ok


def create_account(username: str, password: str) -> AuthResult:
    """First-run Create Account / enrollment. Offline local fallback."""
    if not username.strip() or not password:
        return AuthResult(False, AuthReason.EMPTY_CREDENTIALS, _REASON_MESSAGES[AuthReason.EMPTY_CREDENTIALS])
    bad_u = _validate_username(username)
    if bad_u:
        return AuthResult(False, bad_u, _REASON_MESSAGES[bad_u])
    bad_p = _validate_password(password)
    if bad_p:
        return AuthResult(False, bad_p, _REASON_MESSAGES[bad_p])
    if not enrollment_required():
        return AuthResult(False, AuthReason.ALREADY_ENROLLED, _REASON_MESSAGES[AuthReason.ALREADY_ENROLLED])

    path = _auth_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path.parent, 0o700)
        except OSError:
            pass
        payload = {"username": username.strip(), "verifier": _password_verifier(password)}
        data = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(str(path), flags, 0o600)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            fd = -1
        finally:
            if fd != -1:
                os.close(fd)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return AuthResult(True, AuthReason.OK, "Account created. Log in with the new credential.")
    except FileExistsError:
        return AuthResult(False, AuthReason.ALREADY_ENROLLED, _REASON_MESSAGES[AuthReason.ALREADY_ENROLLED])
    except OSError:
        return AuthResult(False, AuthReason.WRITE_FAILED, _REASON_MESSAGES[AuthReason.WRITE_FAILED])


def login(username: str, password: str) -> AuthResult:
    """Verify enrolled local operator; explicit failure reasons."""
    if not username.strip() or not password:
        return AuthResult(False, AuthReason.EMPTY_CREDENTIALS, _REASON_MESSAGES[AuthReason.EMPTY_CREDENTIALS])
    path = _auth_path()
    if not path.is_file():
        return AuthResult(
            False, AuthReason.ENROLLMENT_REQUIRED, _REASON_MESSAGES[AuthReason.ENROLLMENT_REQUIRED]
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        stored_user = str(payload.get("username", "")).strip()
        verifier = str(payload.get("verifier", ""))
        if not stored_user or not verifier:
            return AuthResult(False, AuthReason.CORRUPT_AUTH_STORE, _REASON_MESSAGES[AuthReason.CORRUPT_AUTH_STORE])
        if username.strip().lower() != stored_user.lower():
            return AuthResult(False, AuthReason.ACCOUNT_NOT_FOUND, _REASON_MESSAGES[AuthReason.ACCOUNT_NOT_FOUND])
        parts = verifier.split("$")
        if len(parts) != 3:
            return AuthResult(False, AuthReason.CORRUPT_AUTH_STORE, _REASON_MESSAGES[AuthReason.CORRUPT_AUTH_STORE])
        iterations, salt_hex, digest_hex = parts
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
            dklen=len(expected),
        )
        if not hmac.compare_digest(digest, expected):
            return AuthResult(False, AuthReason.WRONG_PASSWORD, _REASON_MESSAGES[AuthReason.WRONG_PASSWORD])
        return AuthResult(True, AuthReason.OK, "Authenticated.")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, TypeError):
        return AuthResult(False, AuthReason.CORRUPT_AUTH_STORE, _REASON_MESSAGES[AuthReason.CORRUPT_AUTH_STORE])


def verify_login(username: str, password: str) -> bool:
    return login(username, password).ok


def verify_default_login(username: str, password: str) -> bool:
    """Backward-compatible name — verifies enrolled credentials only (no defaults)."""
    return verify_login(username, password)


def registration_secret_configured() -> bool:
    return bool(os.environ.get(REGISTRATION_SECRET_ENV, "").strip())


def verify_registration_secret(value: str) -> bool:
    expected = os.environ.get(REGISTRATION_SECRET_ENV, "")
    return bool(expected) and hmac.compare_digest(value, expected)
