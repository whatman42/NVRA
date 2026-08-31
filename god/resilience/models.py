"""Phase 4N — N.U.N.G. resilience models. No trading states."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.research.provenance import build_provenance_dict, content_hash
from god.memory.database import utc_now


class RecoveryState(str, Enum):
    NEW = "NEW"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    COMPLETED = "COMPLETED"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    CORRUPTED = "CORRUPTED"
    RECOVERING = "RECOVERING"
    STOPPED = "STOPPED"


class FailureClass(str, Enum):
    DATA_SOURCE_FAILURE = "DATA_SOURCE_FAILURE"
    DATA_VALIDATION_FAILURE = "DATA_VALIDATION_FAILURE"
    STALE_DATA = "STALE_DATA"
    COGNITIVE_FAILURE = "COGNITIVE_FAILURE"
    CHECKPOINT_FAILURE = "CHECKPOINT_FAILURE"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    CORRUPTED_STATE = "CORRUPTED_STATE"
    CONFIGURATION_FAILURE = "CONFIGURATION_FAILURE"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"
    NONE = "NONE"


class JournalEventType(str, Enum):
    CYCLE_STARTED = "cycle_started"
    SNAPSHOT_ACQUIRED = "snapshot_acquired"
    SNAPSHOT_VALIDATED = "snapshot_validated"
    COGNITIVE_CYCLE_STARTED = "cognitive_cycle_started"
    COGNITIVE_CYCLE_COMPLETED = "cognitive_cycle_completed"
    CHECKPOINT_SAVED = "checkpoint_saved"
    CYCLE_COMPLETED = "cycle_completed"
    CYCLE_FAILED = "cycle_failed"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"


@dataclass(frozen=True)
class JournalEntry:
    event_id: str
    cycle_id: str
    timestamp: str
    event_type: JournalEventType
    content_hash: str
    provenance: dict[str, Any]
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "cycle_id": self.cycle_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "content_hash": self.content_hash,
            "provenance": dict(self.provenance),
            "payload": dict(self.payload),
        }


@dataclass
class PersistedCycleRecord:
    cycle_id: str
    snapshot_id: Optional[str]
    recovery_state: RecoveryState
    outcome: str
    content_hash: str
    created_at: str
    updated_at: str
    runtime_version: str
    fingerprint: str
    failure_class: FailureClass = FailureClass.NONE
    provenance: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "recovery_state": self.recovery_state.value,
            "outcome": self.outcome,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "runtime_version": self.runtime_version,
            "fingerprint": self.fingerprint,
            "failure_class": self.failure_class.value,
            "provenance": dict(self.provenance) if self.provenance else None,
            "metadata": dict(self.metadata),
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "PersistedCycleRecord":
        return PersistedCycleRecord(
            cycle_id=d["cycle_id"],
            snapshot_id=d.get("snapshot_id"),
            recovery_state=RecoveryState(d["recovery_state"]),
            outcome=d.get("outcome", ""),
            content_hash=d["content_hash"],
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            runtime_version=d.get("runtime_version", ""),
            fingerprint=d.get("fingerprint", ""),
            failure_class=FailureClass(d.get("failure_class") or "NONE"),
            provenance=d.get("provenance"),
            metadata=dict(d.get("metadata") or {}),
        )


@dataclass
class ResilienceConfig:
    max_cycle_history: int = 100
    max_journal_entries: int = 500
    max_recovery_attempts: int = 3
    max_retries: int = 2
    retry_delay_seconds: float = 0.0
    runtime_version: str = "resilience-4n-v1"
    state_max_age_seconds: Optional[float] = None


def make_event_id(cycle_id: str, event_type: str, payload: dict[str, Any]) -> str:
    return "je-" + content_hash(
        {"c": cycle_id, "t": event_type, "p": payload}
    )[:24]


def make_record_hash(record: dict[str, Any]) -> str:
    body = {
        k: record[k]
        for k in (
            "cycle_id",
            "snapshot_id",
            "recovery_state",
            "outcome",
            "runtime_version",
            "fingerprint",
        )
        if k in record
    }
    return content_hash(body)


def build_resilience_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="resilience_4n", payload=payload)
