"""Local first-run authentication and credential enrollment."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path

REGISTRATION_SECRET_ENV = "NVRA_REGISTRATION_SECRET"
_AUTH_FILE_NAME = "auth_verifier.json"
_PBKDF2_ITERATIONS = 200_000


def user_data_dir() -> Path:
    root = os.environ.get("NVRA_HOME")
    if root:
        return Path(root)
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NVRA"


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


def enroll_first_user(username: str, password: str) -> bool:
    """Create the first local operator credential; never overwrites enrollment."""
    key = username.strip()
    if not key or not password or not enrollment_required():
        return False

    path = _auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    payload = {"username": key, "verifier": _password_verifier(password)}
    data = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    fd = os.open(path, flags, 0o600)
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
    return True


def verify_login(username: str, password: str) -> bool:
    """Verify an enrolled local operator credential; there is no default fallback."""
    path = _auth_path()
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if username.strip().lower() != str(payload["username"]).strip().lower():
            return False
        iterations, salt_hex, digest_hex = str(payload["verifier"]).split("$")
        expected = bytes.fromhex(digest_hex)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
            dklen=len(expected),
        )
        return hmac.compare_digest(digest, expected)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return False


# Backward-compatible public name. It now verifies only enrolled credentials.
def verify_default_login(username: str, password: str) -> bool:
    return verify_login(username, password)


def registration_secret_configured() -> bool:
    return bool(os.environ.get(REGISTRATION_SECRET_ENV, "").strip())


def verify_registration_secret(value: str) -> bool:
    expected = os.environ.get(REGISTRATION_SECRET_ENV, "")
    return bool(expected) and hmac.compare_digest(value, expected)
