"""Phase 6C — N.U.N.G. diagnostic reports. No secrets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .events import EventStore, OperationalEvent
from .health import HealthRegistry
from .metrics import OperationalMetrics
from .models import ComponentHealth, HealthState


@dataclass(frozen=True)
class DiagnosticReport:
    overall_state: HealthState
    components: tuple[ComponentHealth, ...]
    active_failures: tuple[ComponentHealth, ...]
    recent_events: tuple[OperationalEvent, ...]
    last_successful_cycle: str
    last_successful_snapshot: str
    metric_summary: dict[str, int]
    notes: str = "observability_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_state": self.overall_state.value,
            "components": [c.to_dict() for c in self.components],
            "active_failures": [c.to_dict() for c in self.active_failures],
            "recent_events": [e.to_dict() for e in self.recent_events],
            "last_successful_cycle": self.last_successful_cycle,
            "last_successful_snapshot": self.last_successful_snapshot,
            "metric_summary": dict(self.metric_summary),
            "notes": self.notes,
        }


def build_diagnostic(
    health: HealthRegistry,
    events: EventStore,
    metrics: OperationalMetrics,
    *,
    last_successful_cycle: str = "",
    last_successful_snapshot: str = "",
) -> DiagnosticReport:
    comps = health.all()
    failures = tuple(
        c
        for c in comps
        if c.state
        in (
            HealthState.CORRUPTED,
            HealthState.UNAVAILABLE,
            HealthState.STALE,
            HealthState.DEGRADED,
            HealthState.UNKNOWN,
        )
    )
    return DiagnosticReport(
        overall_state=health.overall(),
        components=tuple(comps),
        active_failures=failures,
        recent_events=tuple(events.recent(20)),
        last_successful_cycle=last_successful_cycle,
        last_successful_snapshot=last_successful_snapshot,
        metric_summary=metrics.summary(),
    )
