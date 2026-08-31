"""Runtime state persistence via MemoryStore.set_state (no schema migration)."""

from __future__ import annotations

import json
from typing import Any, Optional

from .models import RuntimeHealth, RuntimeStatus, RuntimeOutcome


class RuntimeStateStore:
    PREFIX = "orch_runtime_v1:"

    def __init__(self, memory_store: Any = None) -> None:
        self._memory = memory_store
        self._health = RuntimeHealth()
        self._local: dict[str, Any] = {}

    @property
    def health(self) -> RuntimeHealth:
        return self._health

    def record_success(
        self,
        *,
        cycle_id: Optional[str],
        snapshot_id: Optional[str],
        at: str,
        outcome: RuntimeOutcome,
    ) -> None:
        self._health.last_cycle_id = cycle_id
        self._health.last_snapshot_id = snapshot_id
        self._health.last_success_at = at
        self._health.last_status = RuntimeStatus.WAITING
        self._health.last_outcome = outcome
        self._health.cycles_completed += 1
        self._persist()

    def record_failure(
        self,
        *,
        at: str,
        outcome: RuntimeOutcome,
        status: RuntimeStatus = RuntimeStatus.FAILED,
    ) -> None:
        self._health.last_failure_at = at
        self._health.last_status = status
        self._health.last_outcome = outcome
        self._health.cycles_failed += 1
        if outcome == RuntimeOutcome.STALE_DATA:
            self._health.stale_data_count += 1
        if outcome == RuntimeOutcome.CORRUPTED:
            self._health.corrupted_checkpoint_count += 1
        self._persist()

    def _persist(self) -> None:
        self._local["health"] = self._health.to_dict()
        if self._memory is not None:
            try:
                self._memory.set_state(
                    self.PREFIX + "health", json.dumps(self._health.to_dict())
                )
            except Exception:
                pass

    def load(self) -> RuntimeHealth:
        if self._memory is not None:
            try:
                raw = self._memory.get_state(self.PREFIX + "health")
                if raw:
                    d = json.loads(raw) if isinstance(raw, str) else raw
                    self._health = RuntimeHealth(
                        last_cycle_id=d.get("last_cycle_id"),
                        last_snapshot_id=d.get("last_snapshot_id"),
                        last_success_at=d.get("last_success_at"),
                        last_failure_at=d.get("last_failure_at"),
                        last_status=RuntimeStatus(
                            d.get("last_status") or "INITIALIZING"
                        ),
                        last_outcome=RuntimeOutcome(d["last_outcome"])
                        if d.get("last_outcome")
                        else None,
                        cycles_completed=int(d.get("cycles_completed") or 0),
                        cycles_failed=int(d.get("cycles_failed") or 0),
                        stale_data_count=int(d.get("stale_data_count") or 0),
                        corrupted_checkpoint_count=int(
                            d.get("corrupted_checkpoint_count") or 0
                        ),
                    )
            except Exception:
                pass
        return self._health
