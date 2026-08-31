"""Phase 6C — N.U.N.G. observability models. Read-only telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from god.research.provenance import content_hash


class HealthState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"


class FailureClass(str, Enum):
    DATA_FAILURE = "DATA_FAILURE"
    DATA_INTEGRITY_FAILURE = "DATA_INTEGRITY_FAILURE"
    STALE_DATA = "STALE_DATA"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    RATE_LIMIT = "RATE_LIMIT"
    CIRCUIT_OPEN = "CIRCUIT_OPEN"
    COGNITIVE_FAILURE = "COGNITIVE_FAILURE"
    PAPER_FAILURE = "PAPER_FAILURE"
    RECOVERY_FAILURE = "RECOVERY_FAILURE"
    READINESS_FAILURE = "READINESS_FAILURE"
    CORRUPTED_STATE = "CORRUPTED_STATE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


class EventType(str, Enum):
    SYSTEM_STARTED = "SYSTEM_STARTED"
    SYSTEM_STOPPED = "SYSTEM_STOPPED"
    HEALTH_CHANGED = "HEALTH_CHANGED"
    DATA_SOURCE_FAILURE = "DATA_SOURCE_FAILURE"
    DATA_SOURCE_RECOVERED = "DATA_SOURCE_RECOVERED"
    SNAPSHOT_ACCEPTED = "SNAPSHOT_ACCEPTED"
    SNAPSHOT_REJECTED = "SNAPSHOT_REJECTED"
    CYCLE_STARTED = "CYCLE_STARTED"
    CYCLE_COMPLETED = "CYCLE_COMPLETED"
    CYCLE_FAILED = "CYCLE_FAILED"
    CYCLE_ABSTAINED = "CYCLE_ABSTAINED"
    PAPER_CYCLE_COMPLETED = "PAPER_CYCLE_COMPLETED"
    READINESS_CHANGED = "READINESS_CHANGED"
    RECOVERY_STARTED = "RECOVERY_STARTED"
    RECOVERY_COMPLETED = "RECOVERY_COMPLETED"


# severity order for aggregation (worst first)
_SEVERITY = {
    HealthState.CORRUPTED: 0,
    HealthState.UNAVAILABLE: 1,
    HealthState.STALE: 2,
    HealthState.DEGRADED: 3,
    HealthState.UNKNOWN: 4,
    HealthState.HEALTHY: 5,
}


@dataclass(frozen=True)
class ComponentHealth:
    component: str
    state: HealthState
    timestamp: str = ""
    reason_codes: tuple[str, ...] = ()
    message: str = ""
    source_reference: str = ""
    cycle_id: str = ""
    snapshot_id: str = ""
    correlation_id: str = ""
    content_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "state": self.state.value,
            "timestamp": self.timestamp,
            "reason_codes": list(self.reason_codes),
            "message": self.message,
            "source_reference": self.source_reference,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "correlation_id": self.correlation_id,
            "content_hash": self.content_hash,
        }


def aggregate_health(components: list[ComponentHealth]) -> HealthState:
    if not components:
        return HealthState.UNKNOWN
    worst = min(components, key=lambda c: _SEVERITY.get(c.state, 4))
    # HEALTHY only if all healthy
    if all(c.state == HealthState.HEALTHY for c in components):
        return HealthState.HEALTHY
    return worst.state


def make_event_id(payload: dict[str, Any]) -> str:
    return "evt-" + content_hash(payload)[:24]


def make_health_snapshot_id(payload: dict[str, Any]) -> str:
    return "hsnap-" + content_hash(payload)[:24]
