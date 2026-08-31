"""Phase 4I — Opportunity selection models. Cognitive attention only. No execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash


class Compatibility(str, Enum):
    COMPATIBLE = "COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class UncertaintyLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class SelectionStatus(str, Enum):
    PENDING = "PENDING"
    EVALUATING = "EVALUATING"
    SELECTED = "SELECTED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_VALID_OPPORTUNITY = "NO_VALID_OPPORTUNITY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    COMPLETE = "COMPLETE"


class SelectionResultStatus(str, Enum):
    SELECTED = "SELECTED"
    NO_VALID_OPPORTUNITY = "NO_VALID_OPPORTUNITY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True)
class Opportunity:
    """Cognitive attention artifact — not an order or position."""

    opportunity_id: str
    candidate_id: str
    instrument_ref: str
    strategy_ref: Optional[str]
    compatibility: Compatibility
    evidence_refs: tuple[str, ...]
    uncertainty: UncertaintyLevel
    attention_rank: int
    selection_status: SelectionStatus
    provenance: dict[str, Any]
    content_hash: str
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "candidate_id": self.candidate_id,
            "instrument_ref": self.instrument_ref,
            "strategy_ref": self.strategy_ref,
            "compatibility": self.compatibility.value,
            "evidence_refs": list(self.evidence_refs),
            "uncertainty": self.uncertainty.value,
            "attention_rank": self.attention_rank,
            "selection_status": self.selection_status.value,
            "provenance": dict(self.provenance),
            "content_hash": self.content_hash,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass
class OpportunitySelectionResult:
    selection_id: str
    status: SelectionResultStatus
    opportunities: list[Opportunity] = field(default_factory=list)
    rejected: list[Opportunity] = field(default_factory=list)
    universe_ref: Optional[str] = None
    discovery_result_id: Optional[str] = None
    selection_version: str = "selection-4i-v1"
    provenance: Optional[dict[str, Any]] = None
    timestamp: str = ""
    truncated: bool = False
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selection_id": self.selection_id,
            "status": self.status.value,
            "opportunities": [o.to_dict() for o in self.opportunities],
            "rejected": [o.to_dict() for o in self.rejected],
            "universe_ref": self.universe_ref,
            "discovery_result_id": self.discovery_result_id,
            "selection_version": self.selection_version,
            "provenance": dict(self.provenance) if self.provenance else None,
            "timestamp": self.timestamp,
            "truncated": self.truncated,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


def make_opportunity_id(
    candidate_id: str,
    strategy_ref: Optional[str],
    compatibility: str,
    uncertainty: str,
) -> str:
    return "opp-" + content_hash(
        {
            "c": candidate_id,
            "s": strategy_ref or "",
            "k": compatibility,
            "u": uncertainty,
        }
    )[:24]


def make_selection_id(
    discovery_result_id: str,
    opportunity_ids: list[str],
    status: str,
    selection_version: str,
) -> str:
    return "sel-" + content_hash(
        {
            "d": discovery_result_id,
            "o": sorted(opportunity_ids),
            "st": status,
            "v": selection_version,
        }
    )[:24]
