"""Circuit breaker for N.U.N.G. market-data transport only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 3
    cooldown_seconds: float = 30.0
    half_open_max_probes: int = 1


class CircuitBreaker:
    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        *,
        now_fn: Optional[callable] = None,
    ) -> None:
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failures = 0
        self._opened_at: Optional[float] = None
        self._half_open_probes = 0
        self._now = now_fn or (lambda: 0.0)

    @property
    def state(self) -> CircuitState:
        self._maybe_transition()
        return self._state

    def allow_request(self) -> bool:
        self._maybe_transition()
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            return False
        # HALF_OPEN
        if self._half_open_probes < self.config.half_open_max_probes:
            self._half_open_probes += 1
            return True
        return False

    def record_success(self) -> None:
        self._failures = 0
        self._half_open_probes = 0
        self._opened_at = None
        self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        self._failures += 1
        if self._state == CircuitState.HALF_OPEN:
            self._trip()
            return
        if self._failures >= self.config.failure_threshold:
            self._trip()

    def _trip(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = float(self._now())
        self._half_open_probes = 0

    def _maybe_transition(self) -> None:
        if self._state != CircuitState.OPEN or self._opened_at is None:
            return
        elapsed = float(self._now()) - self._opened_at
        if elapsed >= self.config.cooldown_seconds:
            self._state = CircuitState.HALF_OPEN
            self._half_open_probes = 0
