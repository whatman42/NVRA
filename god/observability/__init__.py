"""Phase 6C — N.U.N.G. Production Observability.

Read-only telemetry. OBSERVABILITY ≠ EXECUTION. ALLOW ≠ OPEN.
"""

from .models import (
    ComponentHealth,
    EventType,
    FailureClass,
    HealthState,
    aggregate_health,
)
from .metrics import OperationalMetrics
from .events import EventStore, OperationalEvent
from .health import HealthRegistry
from .diagnostics import DiagnosticReport, build_diagnostic
from .snapshots import HealthSnapshot, build_health_snapshot
from .service import ObservabilityService

__all__ = [
    "ComponentHealth",
    "EventType",
    "FailureClass",
    "HealthState",
    "aggregate_health",
    "OperationalMetrics",
    "EventStore",
    "OperationalEvent",
    "HealthRegistry",
    "DiagnosticReport",
    "build_diagnostic",
    "HealthSnapshot",
    "build_health_snapshot",
    "ObservabilityService",
]
