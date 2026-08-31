"""Phase 6C — N.U.N.G. operational events. Bounded, deterministic IDs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import EventType, make_event_id


@dataclass(frozen=True)
class OperationalEvent:
    event_id: str
    event_type: EventType
    timestamp: str
    content_hash: str
    cycle_id: str = ""
    snapshot_id: str = ""
    correlation_id: str = ""
    message: str = ""
    payload: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "correlation_id": self.correlation_id,
            "message": self.message,
            "content_hash": self.content_hash,
            "payload": dict(self.payload) if self.payload else None,
        }


class EventStore:
    def __init__(self, max_events: int = 500) -> None:
        self.max_events = max_events
        self._events: dict[str, OperationalEvent] = {}
        self._order: list[str] = []

    def emit(
        self,
        event_type: EventType,
        *,
        cycle_id: str = "",
        snapshot_id: str = "",
        correlation_id: str = "",
        message: str = "",
        payload: Optional[dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> OperationalEvent:
        ts = timestamp or utc_now()
        body = {
            "event_type": event_type.value,
            "cycle_id": cycle_id,
            "snapshot_id": snapshot_id,
            "correlation_id": correlation_id,
            "message": message,
            "payload": payload or {},
        }
        eid = make_event_id(body)
        if eid in self._events:
            return self._events[eid]
        ev = OperationalEvent(
            event_id=eid,
            event_type=event_type,
            timestamp=ts,
            content_hash=content_hash(body),
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
            correlation_id=correlation_id,
            message=message,
            payload=payload,
        )
        self._events[eid] = ev
        self._order.append(eid)
        while len(self._order) > self.max_events:
            old = self._order.pop(0)
            self._events.pop(old, None)
        return ev

    def recent(self, n: int = 50) -> list[OperationalEvent]:
        ids = self._order[-n:]
        return [self._events[i] for i in ids if i in self._events]
