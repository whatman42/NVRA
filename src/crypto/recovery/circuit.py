"""Recovery circuit breaker — prevents recovery storms."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable


class RecoveryCircuitBreaker:
    def __init__(
        self,
        max_events: int = 5,
        window_seconds: float = 300.0,
        *,
        mono_fn: Callable[[], float] | None = None,
    ) -> None:
        self._max = max_events
        self._window = window_seconds
        self._events: deque[float] = deque()
        self._mono = mono_fn or time.monotonic
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def record(self) -> bool:
        """Record a recovery event. Returns True if storm detected (opens breaker)."""
        now = self._mono()
        self._events.append(now)
        self._prune(now)
        if len(self._events) >= self._max:
            self._open = True
            return True
        return False

    def reset(self) -> None:
        self._events.clear()
        self._open = False

    def _prune(self, now: float) -> None:
        while self._events and (now - self._events[0]) > self._window:
            self._events.popleft()
