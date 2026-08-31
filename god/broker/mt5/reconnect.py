"""Exponential backoff reconnect — pattern used by durable MT bridges."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class BackoffPolicy:
    initial_seconds: float = 1.0
    max_seconds: float = 60.0
    multiplier: float = 2.0
    max_attempts: int = 8


class ReconnectController:
    def __init__(self, policy: Optional[BackoffPolicy] = None) -> None:
        self.policy = policy or BackoffPolicy()
        self.attempts = 0
        self._next_delay = self.policy.initial_seconds

    def reset(self) -> None:
        self.attempts = 0
        self._next_delay = self.policy.initial_seconds

    def next_delay(self) -> float:
        d = self._next_delay
        self._next_delay = min(self.policy.max_seconds, self._next_delay * self.policy.multiplier)
        self.attempts += 1
        return d

    def exhausted(self) -> bool:
        return self.attempts >= self.policy.max_attempts

    def run(
        self,
        connect_fn: Callable[[], bool],
        *,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> bool:
        self.reset()
        while not self.exhausted():
            if connect_fn():
                self.reset()
                return True
            sleep_fn(self.next_delay())
        return False
