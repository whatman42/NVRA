"""Payload validation — reject operational / forbidden fields."""

from __future__ import annotations

from typing import Any

from .models.events import FORBIDDEN_PAYLOAD_KEYS, CognitiveEvent
from .models.context import FORBIDDEN_CONTEXT_STATUS


def validate_payload_ref(payload_ref: dict[str, Any]) -> list[str]:
    """Return list of violation messages (empty = ok)."""
    violations: list[str] = []
    for k, v in payload_ref.items():
        kl = k.lower()
        if kl in FORBIDDEN_PAYLOAD_KEYS:
            violations.append(f"forbidden_key:{k}")
        if isinstance(v, str) and v.upper() in (
            "BUY",
            "SELL",
            "OPEN",
            "CLOSE",
            "MODIFY",
        ):
            # reject operational action strings as values
            violations.append(f"forbidden_value:{k}={v}")
    return violations


def validate_event(event: CognitiveEvent) -> list[str]:
    violations = validate_payload_ref(dict(event.payload_ref))
    if not event.event_id:
        violations.append("missing_event_id")
    if not event.context_id:
        violations.append("missing_context_id")
    if not event.correlation_id:
        violations.append("missing_correlation_id")
    if not event.provenance:
        violations.append("missing_provenance")
    return violations


