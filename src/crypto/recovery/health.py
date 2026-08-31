"""Component health states and heartbeat records."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum, auto


class ComponentClass(Enum):
    CRITICAL = auto()  # execution, risk, supervisor
    NORMAL = auto()  # exchange, market data, reconciliation
    BACKGROUND = auto()  # ML, scanner


class HealthState(Enum):
    HEALTHY = auto()
    DEGRADED = auto()
    SUSPECT = auto()
    UNRESPONSIVE = auto()
    RECOVERING = auto()
    FAILED = auto()
    SAFE_MODE = auto()


@dataclass
class ComponentHealth:
    component_id: str
    component_class: ComponentClass
    health: HealthState = HealthState.HEALTHY
    last_heartbeat_mono: float = 0.0
    last_progress_mono: float = 0.0
    current_operation: str = ""
    operation_start_mono: float | None = None
    consecutive_heartbeat_misses: int = 0
    consecutive_progress_misses: int = 0
    recovery_level: int = 0
    recovery_attempts: int = 0
    last_error: str = ""

    def beat(self, *, mono: float | None = None, operation: str | None = None) -> None:
        now = mono if mono is not None else time.monotonic()
        self.last_heartbeat_mono = now
        self.consecutive_heartbeat_misses = 0
        if operation is not None:
            self.current_operation = operation

    def progress(self, *, mono: float | None = None, operation: str = "") -> None:
        now = mono if mono is not None else time.monotonic()
        self.last_progress_mono = now
        self.consecutive_progress_misses = 0
        if operation:
            self.current_operation = operation
            self.operation_start_mono = now
        # progress implies heartbeat
        self.beat(mono=now)

    def mark_operation(self, operation: str, *, mono: float | None = None) -> None:
        now = mono if mono is not None else time.monotonic()
        self.current_operation = operation
        self.operation_start_mono = now
        self.beat(mono=now)
