"""Strip secrets before any cloud/local job manifest leaves the process."""
from __future__ import annotations

from typing import Any, Mapping

# Keys that must never appear in job manifests, checkpoints, or cloud payloads.
FORBIDDEN_KEY_FRAGMENTS = (
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "private_key",
    "credential",
    "broker",
    "mt5",
    "exchange_key",
    "exchange_secret",
    "live_auth",
    "authorization",
    "windows_credential",
    "keyring",
    "session_cookie",
)


def _is_forbidden_key(key: str) -> bool:
    k = key.lower().replace("-", "_")
    return any(frag in k for frag in FORBIDDEN_KEY_FRAGMENTS)


def sanitize_mapping(data: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a deep-ish copy with forbidden keys removed."""
    if not data:
        return {}
    out: dict[str, Any] = {}
    for key, value in data.items():
        if _is_forbidden_key(str(key)):
            continue
        if isinstance(value, Mapping):
            out[str(key)] = sanitize_mapping(value)
        else:
            out[str(key)] = value
    return out


def assert_no_secrets(data: Mapping[str, Any] | None) -> None:
    """Raise ValueError if forbidden keys remain (for tests / fail-closed checks)."""
    if not data:
        return
    for key, value in data.items():
        if _is_forbidden_key(str(key)):
            raise ValueError(f"forbidden key in compute payload: {key}")
        if isinstance(value, Mapping):
            assert_no_secrets(value)
