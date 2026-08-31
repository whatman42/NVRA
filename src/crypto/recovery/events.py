"""Structured recovery events (no secrets)."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecoveryEvent:
    timestamp_ms: int
    event: str
    component_id: str
    detail: str
    level: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp_ms": self.timestamp_ms,
            "event": self.event,
            "component_id": self.component_id,
            "detail": self.detail[:500],
            "level": self.level,
        }


def make_event(
    event: str,
    component_id: str,
    detail: str = "",
    *,
    level: int = 0,
) -> RecoveryEvent:
    # Sanitize
    safe = detail
    for token in ("api_key", "api_secret", "password", "token", "private_key"):
        if token in safe.lower():
            safe = "[redacted]"
            break
    return RecoveryEvent(
        timestamp_ms=int(time.time() * 1000),
        event=event,
        component_id=component_id,
        detail=safe,
        level=level,
    )
