"""Phase 4J — Cognitive loop models. Attention only. No execution authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.research.provenance import build_provenance_dict, content_hash
from god.memory.database import utc_now


class CycleStatus(str, Enum):
    START = "START"
    DISCOVERING = "DISCOVERING"
    SELECTING = "SELECTING"
    FUSING = "FUSING"
    POLICY = "POLICY"
    ATTENTION = "ATTENTION"
    REASSESSING = "REASSESSING"
    COMPLETE = "COMPLETE"
    NO_VALID_OPPORTUNITY = "NO_VALID_OPPORTUNITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"


class AttentionStatus(str, Enum):
    SELECTED = "SELECTED"
    STILL_VALID = "STILL_VALID"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    NO_LONGER_VALID = "NO_LONGER_VALID"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNKNOWN = "UNKNOWN"


@dataclass
class EvidenceContext:
    """Fused 4D/4E/4F evidence — no fabrication."""

    drift_level: Optional[str] = None
    drift_ref: Optional[str] = None
    regime_label: Optional[str] = None
    regime_ref: Optional[str] = None
    reality_gap_critical: bool = False
    reality_gap_ref: Optional[str] = None
    rca_ref: Optional[str] = None
    policy_permission: Optional[str] = None
    policy_ref: Optional[str] = None
    capital_state: Optional[str] = None
    uncertainty: str = "UNKNOWN"
    evidence_refs: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "drift_level": self.drift_level,
            "drift_ref": self.drift_ref,
            "regime_label": self.regime_label,
            "regime_ref": self.regime_ref,
            "reality_gap_critical": self.reality_gap_critical,
            "reality_gap_ref": self.reality_gap_ref,
            "rca_ref": self.rca_ref,
            "policy_permission": self.policy_permission,
            "policy_ref": self.policy_ref,
            "capital_state": self.capital_state,
            "uncertainty": self.uncertainty,
            "evidence_refs": list(self.evidence_refs),
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


@dataclass
class AttentionItem:
    opportunity_id: str
    instrument_ref: str
    strategy_ref: Optional[str]
    attention_priority: int
    uncertainty: str
    status: AttentionStatus
    evidence_refs: list[str] = field(default_factory=list)
    drift_ref: Optional[str] = None
    regime_ref: Optional[str] = None
    reality_gap_ref: Optional[str] = None
    policy_ref: Optional[str] = None
    candidate_id: Optional[str] = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "instrument_ref": self.instrument_ref,
            "strategy_ref": self.strategy_ref,
            "attention_priority": self.attention_priority,
            "uncertainty": self.uncertainty,
            "status": self.status.value,
            "evidence_refs": list(self.evidence_refs),
            "drift_ref": self.drift_ref,
            "regime_ref": self.regime_ref,
            "reality_gap_ref": self.reality_gap_ref,
            "policy_ref": self.policy_ref,
            "candidate_id": self.candidate_id,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass
class CognitiveAttentionSet:
    set_id: str
    items: list[AttentionItem] = field(default_factory=list)
    status: CycleStatus = CycleStatus.UNKNOWN
    discovery_result_id: Optional[str] = None
    selection_id: Optional[str] = None
    evidence: Optional[EvidenceContext] = None
    provenance: Optional[dict[str, Any]] = None
    timestamp: str = ""
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "set_id": self.set_id,
            "items": [i.to_dict() for i in self.items],
            "status": self.status.value,
            "discovery_result_id": self.discovery_result_id,
            "selection_id": self.selection_id,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "provenance": dict(self.provenance) if self.provenance else None,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }


@dataclass
class CycleResult:
    cycle_id: str
    status: CycleStatus
    attention: Optional[CognitiveAttentionSet] = None
    discovery_result_id: Optional[str] = None
    selection_id: Optional[str] = None
    checkpoint_id: Optional[str] = None
    truncated: bool = False
    stages_completed: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    timestamp: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "status": self.status.value,
            "attention": self.attention.to_dict() if self.attention else None,
            "discovery_result_id": self.discovery_result_id,
            "selection_id": self.selection_id,
            "checkpoint_id": self.checkpoint_id,
            "truncated": self.truncated,
            "stages_completed": list(self.stages_completed),
            "provenance": dict(self.provenance) if self.provenance else None,
            "timestamp": self.timestamp,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


def make_cycle_id(fingerprint: str, version: str = "loop-4j-v1") -> str:
    return "cycle-" + content_hash({"f": fingerprint, "v": version})[:24]


def make_set_id(cycle_id: str, item_ids: list[str]) -> str:
    return "attn-" + content_hash({"c": cycle_id, "i": sorted(item_ids)})[:24]


def build_loop_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="cognitive_loop_4j", payload=payload)
