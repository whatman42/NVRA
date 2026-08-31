"""Recovery helpers for N.U.N.G. — recompute-safe, fail-closed."""

from __future__ import annotations

from typing import Any, Optional

from .models import (
    FailureClass,
    PersistedCycleRecord,
    RecoveryState,
    make_record_hash,
)
from .store import InMemoryRuntimeStateStore


class ResilienceRecovery:
    def __init__(self, store: InMemoryRuntimeStateStore) -> None:
        self.store = store

    def inspect(self, cycle_id: str) -> dict[str, Any]:
        rec = self.store.load(cycle_id)
        if rec is None:
            return {"status": "UNKNOWN", "cycle_id": cycle_id}
        expected = make_record_hash(rec.to_dict())
        if expected != rec.content_hash:
            return {
                "status": "CORRUPTED",
                "cycle_id": cycle_id,
                "reason": "hash_mismatch",
                "failure_class": FailureClass.CORRUPTED_STATE.value,
            }
        if rec.recovery_state == RecoveryState.CORRUPTED:
            return {
                "status": "CORRUPTED",
                "cycle_id": cycle_id,
                "failure_class": FailureClass.CORRUPTED_STATE.value,
            }
        if rec.recovery_state == RecoveryState.COMPLETED:
            return {
                "status": "COMPLETED",
                "cycle_id": cycle_id,
                "outcome": rec.outcome,
                "action": "RETURN_EXISTING",
            }
        if rec.recovery_state == RecoveryState.FAILED:
            return {
                "status": "FAILED",
                "cycle_id": cycle_id,
                "outcome": rec.outcome,
                "action": "DO_NOT_REUSE_AS_SUCCESS",
                "failure_class": rec.failure_class.value,
            }
        return {
            "status": rec.recovery_state.value,
            "cycle_id": cycle_id,
            "action": "RECOMPUTE_FROM_ENTRY",
        }

    def mark_corrupted(self, cycle_id: str) -> Optional[PersistedCycleRecord]:
        rec = self.store.load(cycle_id)
        if rec is None:
            return None
        rec.recovery_state = RecoveryState.CORRUPTED
        rec.failure_class = FailureClass.CORRUPTED_STATE
        d = rec.to_dict()
        rec.content_hash = make_record_hash(d)
        return self.store.save(rec)
