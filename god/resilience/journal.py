"""Append-only runtime journal for N.U.N.G. — not trading events."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now

from .models import (
    JournalEntry,
    JournalEventType,
    ResilienceConfig,
    build_resilience_provenance,
    make_event_id,
)
from god.research.provenance import content_hash


class RuntimeJournal:
    def __init__(
        self,
        config: Optional[ResilienceConfig] = None,
        memory_store: Any = None,
    ) -> None:
        self.config = config or ResilienceConfig()
        self._memory = memory_store
        self._entries: list[JournalEntry] = []
        self._seen: set[str] = set()

    def append(
        self,
        cycle_id: str,
        event_type: JournalEventType,
        payload: Optional[dict[str, Any]] = None,
    ) -> JournalEntry:
        payload = dict(payload or {})
        eid = make_event_id(cycle_id, event_type.value, payload)
        if eid in self._seen:
            for e in self._entries:
                if e.event_id == eid:
                    return e
        body = {
            "event_id": eid,
            "cycle_id": cycle_id,
            "event_type": event_type.value,
            "payload": payload,
        }
        ch = content_hash(body)
        entry = JournalEntry(
            event_id=eid,
            cycle_id=cycle_id,
            timestamp=utc_now(),
            event_type=event_type,
            content_hash=ch,
            provenance=build_resilience_provenance(body),
            payload=payload,
        )
        self._seen.add(eid)
        self._entries.append(entry)
        while len(self._entries) > self.config.max_journal_entries:
            old = self._entries.pop(0)
            self._seen.discard(old.event_id)
        return entry

    def for_cycle(self, cycle_id: str) -> list[JournalEntry]:
        return [e for e in self._entries if e.cycle_id == cycle_id]

    def recent(self, n: int = 50) -> list[JournalEntry]:
        return self._entries[-n:]
