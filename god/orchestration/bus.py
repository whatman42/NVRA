"""In-process bounded EventBus — duplicate suppression, backpressure."""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Optional

from .models.events import CognitiveEvent
from .validation import validate_event


class EventBus:
    def __init__(self, maxsize: int = 1000) -> None:
        self._maxsize = maxsize
        self._queue: deque[CognitiveEvent] = deque()
        self._seen: set[str] = set()
        self._lock = Lock()
        self._dead_letter: list[CognitiveEvent] = []
        self._dropped: int = 0

    def publish(self, event: CognitiveEvent) -> bool:
        """
        Publish event. Returns False if rejected (validation/duplicate/full).
        Duplicate event_id → suppressed (idempotent).
        """
        violations = validate_event(event)
        if violations:
            self._dead_letter.append(event)
            return False
        with self._lock:
            if event.event_id in self._seen:
                return True  # idempotent success, no re-queue
            if len(self._queue) >= self._maxsize:
                self._dropped += 1
                return False  # backpressure
            self._seen.add(event.event_id)
            self._queue.append(event)
            return True

    def consume(self) -> Optional[CognitiveEvent]:
        with self._lock:
            if not self._queue:
                return None
            return self._queue.popleft()

    def pending(self) -> int:
        with self._lock:
            return len(self._queue)

    def is_duplicate(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._seen

    def dead_letters(self) -> list[CognitiveEvent]:
        return list(self._dead_letter)

    def stats(self) -> dict:
        with self._lock:
            return {
                "pending": len(self._queue),
                "seen": len(self._seen),
                "dropped": self._dropped,
                "dead_letters": len(self._dead_letter),
            }
