"""Phase 4O — N.U.N.G. control plane models. Cognitive only. No execution states."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance_dict, content_hash


class ControlState(str, Enum):
    STOPPED = "STOPPED"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    DEGRADED = "DEGRADED"
    CORRUPTED = "CORRUPTED"


class LedgerStage(str, Enum):
    CYCLE_START = "CYCLE_START"
    SNAPSHOT = "SNAPSHOT"
    DISCOVER = "DISCOVER"
    SELECT = "SELECT"
    EVIDENCE = "EVIDENCE"
    ATTENTION = "ATTENTION"
    REASSESS = "REASSESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    ABSTAIN = "ABSTAIN"


class DecisionStatus(str, Enum):
    SELECTED = "SELECTED"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_VALID_OPPORTUNITY = "NO_VALID_OPPORTUNITY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ControlCommandType(str, Enum):
    STATUS = "STATUS"
    PAUSE_COGNITIVE_CYCLE = "PAUSE_COGNITIVE_CYCLE"
    RESUME_COGNITIVE_CYCLE = "RESUME_COGNITIVE_CYCLE"
    FORCE_REASSESS = "FORCE_REASSESS"
    REQUEST_AUDIT = "REQUEST_AUDIT"
    REQUEST_HEALTH = "REQUEST_HEALTH"
    INVALIDATE_CYCLE_CACHE = "INVALIDATE_CYCLE_CACHE"


# Valid transitions (from → set of to)
VALID_TRANSITIONS: dict[ControlState, frozenset[ControlState]] = {
    ControlState.STOPPED: frozenset({ControlState.READY, ControlState.CORRUPTED}),
    ControlState.READY: frozenset(
        {
            ControlState.RUNNING,
            ControlState.PAUSED,
            ControlState.STOPPED,
            ControlState.DEGRADED,
            ControlState.CORRUPTED,
        }
    ),
    ControlState.RUNNING: frozenset(
        {
            ControlState.READY,
            ControlState.PAUSED,
            ControlState.DEGRADED,
            ControlState.CORRUPTED,
            ControlState.STOPPED,
        }
    ),
    ControlState.PAUSED: frozenset(
        {ControlState.READY, ControlState.STOPPED, ControlState.CORRUPTED}
    ),
    ControlState.DEGRADED: frozenset(
        {
            ControlState.READY,
            ControlState.PAUSED,
            ControlState.STOPPED,
            ControlState.CORRUPTED,
        }
    ),
    ControlState.CORRUPTED: frozenset({ControlState.STOPPED}),  # only explicit reset path
}


@dataclass(frozen=True)
class CognitiveExplanation:
    status: DecisionStatus
    reason_codes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    summary: str
    content_hash: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "evidence_refs": list(self.evidence_refs),
            "summary": self.summary,
            "content_hash": self.content_hash,
            "provenance": dict(self.provenance),
        }


@dataclass
class LedgerRecord:
    record_id: str
    cycle_id: str
    correlation_id: str
    stage: LedgerStage
    status: DecisionStatus
    timestamp: str
    content_hash: str
    schema_version: str = "control-ledger-4o-v1"
    snapshot_id: Optional[str] = None
    discovery_result_id: Optional[str] = None
    selection_id: Optional[str] = None
    attention_id: Optional[str] = None
    strategy_ref: Optional[str] = None
    symbol: Optional[str] = None
    opportunity_id: Optional[str] = None
    policy_ref: Optional[str] = None
    drift_ref: Optional[str] = None
    regime_ref: Optional[str] = None
    reality_gap_ref: Optional[str] = None
    reason_code: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    truncated: bool = False
    returned_existing: bool = False
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "cycle_id": self.cycle_id,
            "correlation_id": self.correlation_id,
            "stage": self.stage.value,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "discovery_result_id": self.discovery_result_id,
            "selection_id": self.selection_id,
            "attention_id": self.attention_id,
            "strategy_ref": self.strategy_ref,
            "symbol": self.symbol,
            "opportunity_id": self.opportunity_id,
            "policy_ref": self.policy_ref,
            "drift_ref": self.drift_ref,
            "regime_ref": self.regime_ref,
            "reality_gap_ref": self.reality_gap_ref,
            "reason_code": self.reason_code,
            "provenance": dict(self.provenance) if self.provenance else None,
            "truncated": self.truncated,
            "returned_existing": self.returned_existing,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass
class ControlConfig:
    max_ledger_records: int = 500
    max_audit_records: int = 200
    max_reason_codes: int = 20
    max_evidence_refs: int = 50
    max_trace_events: int = 200
    schema_version: str = "control-4o-v1"


def make_correlation_id(
    snapshot_id: Optional[str],
    cycle_id: Optional[str],
    version: str = "control-4o-v1",
) -> str:
    return "corr-" + content_hash(
        {"s": snapshot_id or "", "c": cycle_id or "", "v": version}
    )[:24]


def make_record_id(payload: dict[str, Any]) -> str:
    return "led-" + content_hash(payload)[:24]


def build_control_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="control_4o", payload=payload)
