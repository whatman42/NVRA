"""Phase 6C — immutable health snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import ComponentHealth, HealthState, make_health_snapshot_id


@dataclass(frozen=True)
class HealthSnapshot:
    snapshot_id: str
    timestamp: str
    overall_state: HealthState
    component_states: tuple[ComponentHealth, ...]
    metric_summary: dict[str, int]
    content_hash: str
    active_incidents: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "overall_state": self.overall_state.value,
            "component_states": [c.to_dict() for c in self.component_states],
            "metric_summary": dict(self.metric_summary),
            "active_incidents": list(self.active_incidents),
            "content_hash": self.content_hash,
        }


def build_health_snapshot(
    overall: HealthState,
    components: list[ComponentHealth],
    metric_summary: dict[str, int],
    *,
    timestamp: Optional[str] = None,
) -> HealthSnapshot:
    ts = timestamp or utc_now()
    incidents = tuple(
        f"{c.component}:{c.state.value}"
        for c in components
        if c.state != HealthState.HEALTHY
    )
    payload = {
        "overall": overall.value,
        "components": [(c.component, c.state.value) for c in sorted(components, key=lambda x: x.component)],
        "metrics": dict(sorted(metric_summary.items())),
        "incidents": list(incidents),
    }
    sid = make_health_snapshot_id(payload)
    return HealthSnapshot(
        snapshot_id=sid,
        timestamp=ts,
        overall_state=overall,
        component_states=tuple(components),
        metric_summary=dict(metric_summary),
        content_hash=content_hash(payload),
        active_incidents=incidents,
    )
