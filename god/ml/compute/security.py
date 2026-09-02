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
    """Return a deep copy with forbidden keys removed from nested structures."""
    if not data:
        return {}
    return _sanitize_value(dict(data))  # type: ignore[return-value]


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            if _is_forbidden_key(str(key)):
                continue
            out[str(key)] = _sanitize_value(item)
        return out
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_value(item) for item in value)
    if isinstance(value, set):
        # Sets of mappings become frozenset of tuples of items for hashability is hard;
        # sanitize members and return a set of sanitized scalars / frozenset markers.
        cleaned = []
        for item in value:
            cleaned.append(_sanitize_value(item))
        try:
            return set(cleaned)
        except TypeError:
            # unhashable after sanitization (e.g. dict) — return list
            return cleaned
    return value


def assert_no_secrets(data: Any) -> None:
    """Raise ValueError if forbidden keys remain anywhere in the structure."""
    if data is None:
        return
    if isinstance(data, Mapping):
        for key, value in data.items():
            if _is_forbidden_key(str(key)):
                raise ValueError(f"forbidden key in compute payload: {key}")
            assert_no_secrets(value)
        return
    if isinstance(data, (list, tuple, set)):
        for item in data:
            assert_no_secrets(item)
