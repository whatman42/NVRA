"""Append-only audit log. Never stores passwords, tokens, or private keys."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import utc_now

# Forbidden field names that must never appear in audit details
_FORBIDDEN = {
    "password",
    "password_hash",
    "private_key",
    "api_key",
    "gemini_key",
    "session_secret",
    "reset_token",
    "token_plaintext",
}


@dataclass
class AuditEvent:
    event_id: str
    actor_id: str
    target_id: str
    action: str
    result: str
    device_id: str
    timestamp: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "actor_id": self.actor_id,
            "target_id": self.target_id,
            "action": self.action,
            "result": self.result,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "details": self.details,
        }


def _sanitize(details: Dict[str, Any]) -> Dict[str, Any]:
    clean: Dict[str, Any] = {}
    for k, v in (details or {}).items():
        if k.lower() in _FORBIDDEN or any(f in k.lower() for f in _FORBIDDEN):
            continue
        if isinstance(v, str) and len(v) > 500:
            v = v[:500] + "…"
        clean[k] = v
    return clean


class AuditLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read(self) -> List[dict]:
        try:
            return list(json.loads(self.path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            return []

    def _write(self, events: List[dict]) -> None:
        # Bound log size to last 10_000 events
        if len(events) > 10_000:
            events = events[-10_000:]
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(events, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def record(
        self,
        *,
        actor_id: str,
        target_id: str,
        action: str,
        result: str,
        device_id: str = "",
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            actor_id=actor_id,
            target_id=target_id,
            action=action,
            result=result,
            device_id=device_id or "",
            timestamp=utc_now(),
            details=_sanitize(details or {}),
        )
        events = self._read()
        events.append(event.to_dict())
        self._write(events)
        return event

    def list_events(
        self,
        *,
        action: Optional[str] = None,
        actor_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[dict]:
        events = self._read()
        if action:
            events = [e for e in events if e.get("action") == action]
        if actor_id:
            events = [e for e in events if e.get("actor_id") == actor_id]
        return events[-limit:]
