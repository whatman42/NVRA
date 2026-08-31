"""Phase 4M — Runtime models for N.U.N.G. Cognitive operation only. No trading states."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class RuntimeStatus(str, Enum):
    INITIALIZING = "INITIALIZING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"


class RuntimeOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    NO_DATA = "NO_DATA"
    STALE_DATA = "STALE_DATA"
    INVALID_DATA = "INVALID_DATA"
    NO_VALID_CANDIDATE = "NO_VALID_CANDIDATE"
    NO_VALID_OPPORTUNITY = "NO_VALID_OPPORTUNITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    CORRUPTED = "CORRUPTED"
    FAILED = "FAILED"
    WAITING = "WAITING"


class FreshnessStatus(str, Enum):
    FRESH = "FRESH"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FreshnessPolicy:
    max_age_seconds: Optional[float] = None
    require_timestamps: bool = False
    allow_partial_universe: bool = True
    fail_on_stale: bool = True
    version: str = "freshness-4m-v1"


@dataclass
class RuntimeConfig:
    interval_seconds: float = 60.0
    max_symbols: int = 500
    max_bars: int = 5000
    min_bars: int = 2
    max_matrix_cells: int = 256
    max_attention: int = 50
    freshness: FreshnessPolicy = field(default_factory=FreshnessPolicy)
    runtime_version: str = "runtime-4m-v1"


@dataclass
class RuntimeHealth:
    last_cycle_id: Optional[str] = None
    last_snapshot_id: Optional[str] = None
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    last_status: RuntimeStatus = RuntimeStatus.INITIALIZING
    last_outcome: Optional[RuntimeOutcome] = None
    cycles_completed: int = 0
    cycles_failed: int = 0
    stale_data_count: int = 0
    corrupted_checkpoint_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "last_cycle_id": self.last_cycle_id,
            "last_snapshot_id": self.last_snapshot_id,
            "last_success_at": self.last_success_at,
            "last_failure_at": self.last_failure_at,
            "last_status": self.last_status.value,
            "last_outcome": self.last_outcome.value if self.last_outcome else None,
            "cycles_completed": self.cycles_completed,
            "cycles_failed": self.cycles_failed,
            "stale_data_count": self.stale_data_count,
            "corrupted_checkpoint_count": self.corrupted_checkpoint_count,
        }


@dataclass
class RuntimeResult:
    status: RuntimeStatus
    outcome: RuntimeOutcome
    cycle_id: Optional[str] = None
    snapshot_id: Optional[str] = None
    discovery_result_id: Optional[str] = None
    selection_id: Optional[str] = None
    attention_set_id: Optional[str] = None
    next_run_at: Optional[str] = None
    wait_seconds: Optional[float] = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "outcome": self.outcome.value,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "discovery_result_id": self.discovery_result_id,
            "selection_id": self.selection_id,
            "attention_set_id": self.attention_set_id,
            "next_run_at": self.next_run_at,
            "wait_seconds": self.wait_seconds,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }
