"""Phase 6C — N.U.N.G. component health registry."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .models import ComponentHealth, HealthState, aggregate_health


class HealthRegistry:
    def __init__(self) -> None:
        self._components: dict[str, ComponentHealth] = {}

    def set(
        self,
        component: str,
        state: HealthState,
        *,
        reason_codes: tuple[str, ...] = (),
        message: str = "",
        source_reference: str = "",
        cycle_id: str = "",
        snapshot_id: str = "",
        correlation_id: str = "",
        timestamp: Optional[str] = None,
    ) -> ComponentHealth:
        ts = timestamp or utc_now()
        payload = {
            "component": component,
            "state": state.value,
            "reason_codes": list(reason_codes),
            "cycle_id": cycle_id,
            "snapshot_id": snapshot_id,
        }
        rec = ComponentHealth(
            component=component,
            state=state,
            timestamp=ts,
            reason_codes=reason_codes,
            message=message,
            source_reference=source_reference,
            cycle_id=cycle_id,
            snapshot_id=snapshot_id,
            correlation_id=correlation_id,
            content_hash=content_hash(payload),
        )
        self._components[component] = rec
        return rec

    def get(self, component: str) -> Optional[ComponentHealth]:
        return self._components.get(component)

    def all(self) -> list[ComponentHealth]:
        return list(self._components.values())

    def overall(self) -> HealthState:
        return aggregate_health(self.all())
