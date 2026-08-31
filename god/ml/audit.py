"""Structured ML audit trail — promotion, rollback, train, inference gates.

Append-only in-memory + optional JSONL file. Never stores secrets or orders.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AuditEntry:
    ts: str
    event_type: str  # promote | rollback | train | inference_gate | health | recovery
    actor: str = "ml_system"
    model_id: str = ""
    model_version: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    outcome: str = ""  # allowed | denied | success | failed | deferred

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "event_type": self.event_type,
            "actor": self.actor,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "detail": dict(self.detail),
            "outcome": self.outcome,
        }


class MLAuditTrail:
    """Ring-buffer + optional durable JSONL. Fail-closed on write errors."""

    def __init__(self, max_entries: int = 1000, path: Optional[Path] = None) -> None:
        self._buf: deque[AuditEntry] = deque(maxlen=max_entries)
        self._path = Path(path) if path else None

    def record(
        self,
        event_type: str,
        *,
        model_id: str = "",
        model_version: str = "",
        detail: Optional[dict[str, Any]] = None,
        outcome: str = "",
        actor: str = "ml_system",
    ) -> AuditEntry:
        entry = AuditEntry(
            ts=_utc_now(),
            event_type=event_type,
            actor=actor,
            model_id=model_id,
            model_version=model_version,
            detail=dict(detail or {}),
            outcome=outcome,
        )
        self._buf.append(entry)
        if self._path is not None:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
            except OSError:
                pass  # fail-closed: memory still holds entry
        return entry

    def recent(self, n: int = 50) -> list[dict[str, Any]]:
        return [e.to_dict() for e in list(self._buf)[-n:]]

    def by_type(self, event_type: str, n: int = 50) -> list[dict[str, Any]]:
        matched = [e for e in self._buf if e.event_type == event_type]
        return [e.to_dict() for e in matched[-n:]]
