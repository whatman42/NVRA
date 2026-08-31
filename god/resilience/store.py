"""N.U.N.G. runtime cycle persistence — MemoryStore JSON or in-memory. No schema migration."""

from __future__ import annotations

import json
from typing import Any, Optional

from god.memory.database import utc_now

from .models import (
    PersistedCycleRecord,
    RecoveryState,
    ResilienceConfig,
    make_record_hash,
    build_resilience_provenance,
)


class InMemoryRuntimeStateStore:
    """Bounded cycle history. Process-local + optional MemoryStore mirror."""

    PREFIX = "orch_resilience_v1:"

    def __init__(
        self,
        config: Optional[ResilienceConfig] = None,
        memory_store: Any = None,
    ) -> None:
        self.config = config or ResilienceConfig()
        self._memory = memory_store
        self._by_id: dict[str, PersistedCycleRecord] = {}
        self._order: list[str] = []

    def save(self, record: PersistedCycleRecord) -> PersistedCycleRecord:
        # verify hash matches content
        d = record.to_dict()
        expected = make_record_hash(d)
        if record.content_hash != expected:
            # recompute for consistency
            record = PersistedCycleRecord(
                cycle_id=record.cycle_id,
                snapshot_id=record.snapshot_id,
                recovery_state=record.recovery_state,
                outcome=record.outcome,
                content_hash=expected,
                created_at=record.created_at or utc_now(),
                updated_at=utc_now(),
                runtime_version=record.runtime_version,
                fingerprint=record.fingerprint,
                failure_class=record.failure_class,
                provenance=record.provenance
                or build_resilience_provenance({"cycle_id": record.cycle_id}),
                metadata=dict(record.metadata),
            )
        if record.cycle_id in self._by_id:
            existing = self._by_id[record.cycle_id]
            if existing.recovery_state == RecoveryState.COMPLETED:
                return existing  # RETURN_EXISTING success
            record.created_at = existing.created_at
            record.updated_at = utc_now()
        else:
            if not record.created_at:
                record.created_at = utc_now()
            record.updated_at = utc_now()
            self._order.append(record.cycle_id)
        self._by_id[record.cycle_id] = record
        self._trim()
        self._mirror(record)
        return record

    def load(self, cycle_id: str) -> Optional[PersistedCycleRecord]:
        if cycle_id in self._by_id:
            return self._by_id[cycle_id]
        if self._memory is None:
            return None
        try:
            raw = self._memory.get_state(self.PREFIX + "cycle:" + cycle_id)
            if not raw:
                return None
            d = json.loads(raw) if isinstance(raw, str) else raw
            rec = PersistedCycleRecord.from_dict(d)
            if make_record_hash(rec.to_dict()) != rec.content_hash:
                return None  # treat as missing / corrupt
            self._by_id[cycle_id] = rec
            return rec
        except Exception:
            return None

    def exists(self, cycle_id: str) -> bool:
        return self.load(cycle_id) is not None

    def delete(self, cycle_id: str) -> None:
        self._by_id.pop(cycle_id, None)
        self._order = [c for c in self._order if c != cycle_id]

    def list_recent(self, n: int = 20) -> list[PersistedCycleRecord]:
        ids = self._order[-n:]
        return [self._by_id[i] for i in ids if i in self._by_id]

    def latest_completed(self) -> Optional[PersistedCycleRecord]:
        for cid in reversed(self._order):
            r = self._by_id.get(cid)
            if r and r.recovery_state == RecoveryState.COMPLETED:
                return r
        return None

    def latest_failed(self) -> Optional[PersistedCycleRecord]:
        for cid in reversed(self._order):
            r = self._by_id.get(cid)
            if r and r.recovery_state in (RecoveryState.FAILED, RecoveryState.CORRUPTED):
                return r
        return None

    def _trim(self) -> None:
        while len(self._order) > self.config.max_cycle_history:
            old = self._order.pop(0)
            self._by_id.pop(old, None)

    def _mirror(self, record: PersistedCycleRecord) -> None:
        if self._memory is None:
            return
        try:
            self._memory.set_state(
                self.PREFIX + "cycle:" + record.cycle_id,
                json.dumps(record.to_dict()),
            )
            self._memory.set_state(
                self.PREFIX + "latest",
                record.cycle_id,
            )
        except Exception:
            pass
