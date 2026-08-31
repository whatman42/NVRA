"""Network chaos helpers — simulated failures with backoff (no request storms)."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class NetworkFault(Enum):
    NONE = auto()
    LATENCY = auto()
    TIMEOUT = auto()
    DNS = auto()
    RESET = auto()
    HALF_OPEN = auto()
    INTERMITTENT = auto()


@dataclass
class ChaosNetwork:
    """Injectable transport fault injector with retry budget."""

    fault: NetworkFault = NetworkFault.NONE
    latency_ms: float = 0.0
    fail_rate: float = 0.0
    seed: int = 1
    max_retries: int = 5
    base_backoff_s: float = 0.05
    _rng: random.Random = field(init=False)
    attempts: int = 0
    successes: int = 0

    def __post_init__(self) -> None:
        self._rng = random.Random(self.seed)

    def call(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Execute fn with faults + exponential backoff. Raises after budget."""
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self.attempts += 1
            if self.fault is NetworkFault.DNS and attempt == 0:
                last_exc = OSError("dns failure")
                self._sleep(attempt)
                continue
            if self.fault is NetworkFault.HALF_OPEN:
                # First success then hang/timeout pattern
                if self.successes == 0:
                    self.successes += 1
                    return fn(*args, **kwargs)
                last_exc = TimeoutError("half-open timeout")
                self._sleep(attempt)
                continue
            if self.fault is NetworkFault.TIMEOUT or (
                self.fail_rate > 0 and self._rng.random() < self.fail_rate
            ):
                last_exc = TimeoutError("simulated timeout")
                self._sleep(attempt)
                continue
            if self.fault is NetworkFault.RESET and attempt < 2:
                last_exc = ConnectionResetError("connection reset")
                self._sleep(attempt)
                continue
            if self.latency_ms > 0 or self.fault is NetworkFault.LATENCY:
                time.sleep(min(0.05, self.latency_ms / 1000.0))  # capped in tests
            self.successes += 1
            return fn(*args, **kwargs)
        assert last_exc is not None
        raise last_exc

    def _sleep(self, attempt: int) -> None:
        delay = self.base_backoff_s * (2**attempt)
        # jitter
        delay *= 0.5 + self._rng.random()
        time.sleep(min(0.1, delay))  # keep unit tests fast


@dataclass
class TimeSync:
    """Exchange server-time delta tracking — do not raw-trust local wall clock."""

    local_offset_ms: int = 0  # local - exchange
    last_exchange_ms: int | None = None

    def calibrate(self, exchange_server_ms: int, local_ms: int) -> int:
        self.local_offset_ms = local_ms - exchange_server_ms
        self.last_exchange_ms = exchange_server_ms
        return self.local_offset_ms

    def to_exchange(self, local_ms: int) -> int:
        return local_ms - self.local_offset_ms

    def reject_stale_timestamp(
        self, api_ts_ms: int, now_exchange_ms: int, max_skew_ms: int = 5000
    ) -> bool:
        """True if API timestamp should be rejected."""
        return abs(api_ts_ms - now_exchange_ms) > max_skew_ms
