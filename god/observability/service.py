"""Phase 6C — N.U.N.G. ObservabilityService. Read-only; never grants authority."""

from __future__ import annotations

from typing import Any

from .diagnostics import DiagnosticReport, build_diagnostic
from .events import EventStore, OperationalEvent
from .health import HealthRegistry
from .metrics import OperationalMetrics
from .models import EventType, HealthState
from .snapshots import HealthSnapshot, build_health_snapshot


class ObservabilityService:
    """
    Collects health, metrics, events. Does not mutate cognitive/paper state.
    OBSERVABILITY FAILURE ≠ TRADING PERMISSION.
    """

    def __init__(
        self,
        *,
        max_events: int = 500,
        max_health_history: int = 100,
    ) -> None:
        self.health = HealthRegistry()
        self.metrics = OperationalMetrics()
        self.events = EventStore(max_events=max_events)
        self.max_health_history = max_health_history
        self._health_history: list[HealthSnapshot] = []
        self.last_successful_cycle: str = ""
        self.last_successful_snapshot: str = ""

    def record_component(
        self,
        component: str,
        state: HealthState,
        **kwargs: Any,
    ) -> None:
        self.health.set(component, state, **kwargs)

    def emit(self, event_type: EventType, **kwargs: Any) -> OperationalEvent:
        return self.events.emit(event_type, **kwargs)

    def mark_cycle_completed(self, cycle_id: str) -> None:
        self.metrics.inc("cycles_completed")
        self.last_successful_cycle = cycle_id
        self.emit(EventType.CYCLE_COMPLETED, cycle_id=cycle_id)

    def mark_cycle_failed(self, cycle_id: str = "") -> None:
        self.metrics.inc("cycles_failed")
        self.emit(EventType.CYCLE_FAILED, cycle_id=cycle_id)

    def mark_snapshot_valid(self, snapshot_id: str = "") -> None:
        self.metrics.inc("snapshots_received")
        self.metrics.inc("snapshots_valid")
        self.last_successful_snapshot = snapshot_id
        self.emit(EventType.SNAPSHOT_ACCEPTED, snapshot_id=snapshot_id)

    def mark_snapshot_invalid(self, snapshot_id: str = "") -> None:
        self.metrics.inc("snapshots_received")
        self.metrics.inc("snapshots_invalid")
        self.emit(EventType.SNAPSHOT_REJECTED, snapshot_id=snapshot_id)

    def mark_provider_failure(self) -> None:
        self.metrics.inc("provider_failures")
        self.emit(EventType.DATA_SOURCE_FAILURE)
        self.record_component("data_source", HealthState.UNAVAILABLE, reason_codes=("provider_failure",))

    def mark_readiness(self, passed: bool) -> None:
        self.metrics.inc("readiness_checks")
        if passed:
            self.metrics.inc("readiness_passed")
        else:
            self.metrics.inc("readiness_failed")
        self.emit(EventType.READINESS_CHANGED, message="passed" if passed else "failed")

    def overall_health(self) -> HealthState:
        return self.health.overall()

    def health_snapshot(self) -> HealthSnapshot:
        snap = build_health_snapshot(
            self.health.overall(),
            self.health.all(),
            self.metrics.summary(),
        )
        self._health_history.append(snap)
        while len(self._health_history) > self.max_health_history:
            self._health_history.pop(0)
        return snap

    def diagnose(self) -> DiagnosticReport:
        return build_diagnostic(
            self.health,
            self.events,
            self.metrics,
            last_successful_cycle=self.last_successful_cycle,
            last_successful_snapshot=self.last_successful_snapshot,
        )
