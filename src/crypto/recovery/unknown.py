"""UNKNOWN order recovery — never treat timeout as failure/success."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto

from crypto.recovery.config import RecoveryConfig
from crypto.recovery.events import RecoveryEvent, make_event


class UnknownResolution(Enum):
    PENDING = auto()
    FOUND_FILLED = auto()
    FOUND_OPEN = auto()
    FOUND_CANCELLED = auto()
    FOUND_REJECTED = auto()
    FOUND_FAILED = auto()
    UNRESOLVED = auto()


# Query function: (execution_id) -> status string or None if not found
OrderQueryFn = Callable[[str], str | None]


@dataclass
class UnknownOrderTracker:
    execution_id: str
    client_order_id: str
    started_mono: float
    attempts: int = 0
    resolution: UnknownResolution = UnknownResolution.PENDING
    last_detail: str = ""
    events: list[RecoveryEvent] = field(default_factory=list)


class UnknownOrderResolver:
    """Asynchronous verification schedule. Never auto-resubmits."""

    def __init__(self, config: RecoveryConfig | None = None) -> None:
        self._cfg = config or RecoveryConfig()
        self._trackers: dict[str, UnknownOrderTracker] = {}

    def track(
        self,
        execution_id: str,
        client_order_id: str,
        *,
        mono: float | None = None,
    ) -> UnknownOrderTracker:
        now = mono if mono is not None else time.monotonic()
        t = UnknownOrderTracker(
            execution_id=execution_id,
            client_order_id=client_order_id,
            started_mono=now,
        )
        t.events.append(make_event("UNKNOWN_ORDER", execution_id, f"client={client_order_id}"))
        self._trackers[execution_id] = t
        return t

    def get(self, execution_id: str) -> UnknownOrderTracker | None:
        return self._trackers.get(execution_id)

    def should_query(self, execution_id: str, *, mono: float | None = None) -> bool:
        t = self._trackers.get(execution_id)
        if t is None or t.resolution is not UnknownResolution.PENDING:
            return False
        now = mono if mono is not None else time.monotonic()
        elapsed = now - t.started_mono
        schedule = self._cfg.unknown_verify_schedule
        if t.attempts >= len(schedule):
            return False
        return elapsed >= schedule[t.attempts]

    def query_once(
        self,
        execution_id: str,
        query_fn: OrderQueryFn,
        *,
        mono: float | None = None,
        retry_after_seconds: float | None = None,
    ) -> UnknownResolution:
        """Perform one verification attempt. Respect Retry-After if provided."""
        t = self._trackers.get(execution_id)
        if t is None:
            return UnknownResolution.UNRESOLVED
        if t.resolution is not UnknownResolution.PENDING:
            return t.resolution

        now = mono if mono is not None else time.monotonic()
        if retry_after_seconds is not None and retry_after_seconds > 0:
            # defer — do not increment attempt as failed hard
            t.last_detail = f"retry_after={retry_after_seconds}"
            t.events.append(make_event("UNKNOWN_ORDER_RETRY", execution_id, t.last_detail))
            return UnknownResolution.PENDING

        if not self.should_query(execution_id, mono=now):
            return UnknownResolution.PENDING

        t.attempts += 1
        t.events.append(make_event("UNKNOWN_ORDER_RETRY", execution_id, f"attempt={t.attempts}"))
        try:
            status = query_fn(execution_id)
        except Exception as exc:  # noqa: BLE001
            t.last_detail = type(exc).__name__
            return self._maybe_unresolved(t, now)

        if status is None:
            # not found yet — may still appear
            return self._maybe_unresolved(t, now)

        status_l = status.lower()
        mapping = {
            "filled": UnknownResolution.FOUND_FILLED,
            "closed": UnknownResolution.FOUND_FILLED,
            "open": UnknownResolution.FOUND_OPEN,
            "new": UnknownResolution.FOUND_OPEN,
            "live": UnknownResolution.FOUND_OPEN,
            "canceled": UnknownResolution.FOUND_CANCELLED,
            "cancelled": UnknownResolution.FOUND_CANCELLED,
            "rejected": UnknownResolution.FOUND_REJECTED,
            "failed": UnknownResolution.FOUND_FAILED,
            "expired": UnknownResolution.FOUND_CANCELLED,
        }
        resolution = mapping.get(status_l)
        if resolution is None:
            return self._maybe_unresolved(t, now)

        t.resolution = resolution
        t.events.append(
            make_event(
                "UNKNOWN_ORDER_RESOLVED",
                execution_id,
                f"resolution={resolution.name}",
            )
        )
        return resolution

    def _maybe_unresolved(self, t: UnknownOrderTracker, now: float) -> UnknownResolution:
        schedule = self._cfg.unknown_verify_schedule
        if t.attempts >= len(schedule):
            t.resolution = UnknownResolution.UNRESOLVED
            t.events.append(
                make_event(
                    "UNKNOWN_ORDER_UNRESOLVED",
                    t.execution_id,
                    "verification window exhausted",
                )
            )
            return UnknownResolution.UNRESOLVED
        return UnknownResolution.PENDING

    def blocks_duplicate(self, client_order_id: str) -> bool:
        """True if any pending/unresolved tracker shares client_order_id."""
        for t in self._trackers.values():
            if t.client_order_id == client_order_id and t.resolution in (
                UnknownResolution.PENDING,
                UnknownResolution.UNRESOLVED,
                UnknownResolution.FOUND_OPEN,
            ):
                return True
        return False
