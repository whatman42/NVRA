"""Startup recovery sequence — rate-limited, priority ordered."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from crypto.recovery.config import RecoveryConfig
from crypto.recovery.events import RecoveryEvent, make_event


class StartupPhase(Enum):
    LOAD_STATE = auto()
    VALIDATE_DB = auto()
    START_SUPERVISOR = auto()
    CONNECT_EXCHANGE = auto()
    HEALTH_CHECK = auto()
    FETCH_BALANCES = auto()
    FETCH_OPEN_ORDERS = auto()
    FETCH_TRADES = auto()
    RECONCILE_EXECUTIONS = auto()
    RECONCILE_PORTFOLIO = auto()
    VALIDATE_MARKET_DATA = auto()
    RISK_EVAL = auto()
    READY = auto()
    PARTIAL = auto()
    SAFE_MODE = auto()
    FAILED = auto()


class TaskPriority(Enum):
    P0 = 0  # execution reconciliation
    P1 = 1  # balances / open orders
    P2 = 2  # trades
    P3 = 3  # market metadata
    P4 = 4  # analytics


@dataclass
class StartupTask:
    name: str
    priority: TaskPriority
    fn: Callable[[], bool]  # returns True if ok
    done: bool = False
    ok: bool = False
    error: str = ""


@dataclass
class StartupResult:
    phase: StartupPhase
    tasks: list[StartupTask] = field(default_factory=list)
    events: list[RecoveryEvent] = field(default_factory=list)
    trading_allowed: bool = False
    partial: bool = False

    @property
    def safe_to_trade(self) -> bool:
        return self.trading_allowed and not self.partial and self.phase is StartupPhase.READY


class StartupRecovery:
    """Ordered, rate-limited startup. Trading blocked until safe."""

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        self._cfg = config or RecoveryConfig()
        self._last_request_mono = 0.0
        self._events: list[RecoveryEvent] = []

    def run(
        self,
        tasks: list[StartupTask],
        *,
        mono_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> StartupResult:
        mono = mono_fn or time.monotonic
        sleep = sleep_fn or time.sleep
        ordered = sorted(tasks, key=lambda t: t.priority.value)
        result = StartupResult(phase=StartupPhase.LOAD_STATE, tasks=ordered)

        self._events.append(make_event("RECONCILIATION_STARTED", "startup", "begin"))

        for task in ordered:
            # rate limit
            now = mono()
            elapsed = now - self._last_request_mono
            wait = self._cfg.startup_min_interval_seconds - elapsed
            if wait > 0:
                sleep(wait)
            self._last_request_mono = mono()

            try:
                ok = task.fn()
                task.done = True
                task.ok = bool(ok)
            except Exception as exc:  # noqa: BLE001
                task.done = True
                task.ok = False
                task.error = type(exc).__name__
                if "429" in str(exc) or "rate" in str(exc).lower():
                    # backoff
                    sleep(self._cfg.level2_base_seconds)
                    self._events.append(
                        make_event("RECOVERY_RETRY", "startup", f"rate_limit {task.name}")
                    )
                    try:
                        ok = task.fn()
                        task.ok = bool(ok)
                    except Exception as exc2:  # noqa: BLE001
                        task.ok = False
                        task.error = type(exc2).__name__

        # Evaluate completeness
        p0 = [t for t in ordered if t.priority is TaskPriority.P0]
        p1 = [t for t in ordered if t.priority is TaskPriority.P1]
        p0_ok = all(t.ok for t in p0) if p0 else True
        p1_ok = all(t.ok for t in p1) if p1 else True

        if p0_ok and p1_ok:
            result.phase = StartupPhase.READY
            result.trading_allowed = True
            result.partial = False
            self._events.append(make_event("RECONCILIATION_SUCCESS", "startup", "ready"))
        elif p0_ok or p1_ok:
            result.phase = StartupPhase.PARTIAL
            result.trading_allowed = False
            result.partial = True
            self._events.append(make_event("RECONCILIATION_PARTIAL", "startup", "partial"))
        else:
            result.phase = StartupPhase.SAFE_MODE
            result.trading_allowed = False
            result.partial = True
            self._events.append(make_event("SAFE_MODE_ENTERED", "startup", "reconciliation failed"))

        result.events = list(self._events)
        return result
