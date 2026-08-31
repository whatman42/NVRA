"""Centralized notification queue — engines never call Telegram HTTP directly."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import IntEnum


class NotifyPriority(IntEnum):
    P0 = 0  # emergency, security
    P1 = 1  # fills, risk warnings
    P2 = 2  # recovery, connectivity, ML, governor
    P3 = 3  # telemetry


@dataclass(frozen=True, slots=True)
class Notification:
    priority: NotifyPriority
    event: str
    message: str
    timestamp_ms: int
    dedupe_key: str = ""


@dataclass
class NotifyQueue:
    """Priority queue with dedupe, rate limit, aggregation."""

    max_size: int = 500
    rate_per_minute: int = 20
    aggregate_window_seconds: float = 20.0
    _items: list[Notification] = field(default_factory=list)
    _sent_times: deque[float] = field(default_factory=deque)
    _recent_keys: dict[str, list[float]] = field(default_factory=dict)
    _mono: Callable[[], float] = time.monotonic

    def publish(
        self,
        event: str,
        message: str,
        *,
        priority: NotifyPriority = NotifyPriority.P3,
        dedupe_key: str = "",
    ) -> None:
        # redact secrets
        safe = message
        for token in ("api_key", "api_secret", "bot_token", "password", "pin"):
            if token in safe.lower():
                safe = "[redacted]"
                break
        now_ms = int(time.time() * 1000)
        key = dedupe_key or f"{event}:{safe[:40]}"
        mono = self._mono()
        # aggregation
        times = self._recent_keys.setdefault(key, [])
        times.append(mono)
        times[:] = [t for t in times if mono - t <= self.aggregate_window_seconds]
        if len(times) >= 3:
            safe = f"{event} unstable: {len(times)} events in {self.aggregate_window_seconds:.0f}s"
            # replace prior pending same key
            self._items = [n for n in self._items if n.dedupe_key != key]
        n = Notification(priority, event, safe, now_ms, key)
        self._items.append(n)
        self._items.sort(key=lambda x: (x.priority, x.timestamp_ms))
        if len(self._items) > self.max_size:
            # drop lowest priority (highest enum value) first
            self._items = sorted(self._items, key=lambda x: (x.priority, x.timestamp_ms))[
                : self.max_size
            ]

    def pop_ready(self) -> Notification | None:
        """Rate-limited pop. P0 never starved by waiting for lower priority."""
        if not self._items:
            return None
        mono = self._mono()
        # prune sent window
        while self._sent_times and mono - self._sent_times[0] > 60.0:
            self._sent_times.popleft()
        # always allow P0 even at rate limit
        p0 = next((i for i, n in enumerate(self._items) if n.priority is NotifyPriority.P0), None)
        if p0 is not None:
            n = self._items.pop(p0)
            self._sent_times.append(mono)
            return n
        if len(self._sent_times) >= self.rate_per_minute:
            return None
        n = self._items.pop(0)
        self._sent_times.append(mono)
        return n

    def pending_count(self) -> int:
        return len(self._items)

    def pending_by_priority(self) -> dict[int, int]:
        out: dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
        for n in self._items:
            out[int(n.priority)] = out.get(int(n.priority), 0) + 1
        return out
