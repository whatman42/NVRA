"""Control-plane audit — never records secrets or PIN."""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class AuditEntry:
    timestamp_ms: int
    actor: str
    action: str
    result: str
    detail: str = ""


@dataclass
class ControlAuditLog:
    max_entries: int = 500
    _entries: list[AuditEntry] = field(default_factory=list)

    def record(
        self,
        actor: str,
        action: str,
        result: str,
        detail: str = "",
    ) -> None:
        safe = detail
        for token in (
            "api_key",
            "api_secret",
            "telegram",
            "token",
            "password",
            "pin",
            "secret",
        ):
            if token in safe.lower():
                safe = "[redacted]"
                break
        self._entries.append(
            AuditEntry(
                timestamp_ms=int(time.time() * 1000),
                actor=actor,
                action=action,
                result=result,
                detail=safe[:500],
            )
        )
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries // 2 :]

    def recent(self, n: int = 50) -> list[AuditEntry]:
        return list(self._entries[-n:])
