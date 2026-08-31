"""Phase 4D — Failure & RCA models.

Evidence-based assessment. Unknown is valid. No execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash

from .taxonomy import CausalStatus, CauseCategory, CauseRole


class FailureSeverity(str, Enum):
    """Descriptive severity — never a trading disable gate."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class FailureStatus(str, Enum):
    OPEN = "OPEN"
    UNDER_ANALYSIS = "UNDER_ANALYSIS"
    ASSESSED = "ASSESSED"
    CLOSED = "CLOSED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True)
class CauseHypothesis:
    """A single hypothesized or confirmed cause with epistemic status."""

    cause_id: str
    category: CauseCategory
    role: CauseRole
    causal_status: CausalStatus
    description: str = ""
    evidence_refs: tuple[str, ...] = ()
    descriptive_weight: Optional[float] = None  # descriptive only, not objective %
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cause_id": self.cause_id,
            "category": self.category.value,
            "role": self.role.value,
            "causal_status": self.causal_status.value,
            "description": self.description,
            "evidence_refs": list(self.evidence_refs),
            "descriptive_weight": self.descriptive_weight,
            "metadata": dict(self.metadata),
        }


@dataclass
class FailureEvent:
    """Typed failure representation — retained forever (anti-survivorship)."""

    failure_id: str
    timestamp: str
    source: str
    strategy_ref: Optional[str] = None
    strategy_version: Optional[int] = None
    experiment_ref: Optional[str] = None
    expected_behavior: Optional[str] = None
    observed_behavior: Optional[str] = None
    severity: FailureSeverity = FailureSeverity.UNKNOWN
    evidence_refs: list[str] = field(default_factory=list)
    gap_refs: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    status: FailureStatus = FailureStatus.OPEN
    candidate_causes: list[CauseHypothesis] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "timestamp": self.timestamp,
            "source": self.source,
            "strategy_ref": self.strategy_ref,
            "strategy_version": self.strategy_version,
            "experiment_ref": self.experiment_ref,
            "expected_behavior": self.expected_behavior,
            "observed_behavior": self.observed_behavior,
            "severity": self.severity.value,
            "evidence_refs": list(self.evidence_refs),
            "gap_refs": list(self.gap_refs),
            "provenance": dict(self.provenance) if self.provenance else None,
            "status": self.status.value,
            "candidate_causes": [c.to_dict() for c in self.candidate_causes],
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    def has_execution_intent(self) -> bool:
        blob = " ".join(
            [self.source, self.notes, str(list(self.metadata.keys()))]
        ).lower()
        return any(
            t in blob
            for t in ("op_buy", "op_sell", "ordersend", "lot_size", "allocate capital")
        )


@dataclass
class RootCauseAssessment:
    """RCA result — evidence chain preserved. Unknown is valid."""

    assessment_id: str
    failure_id: str
    timestamp: str
    primary_candidate: Optional[CauseHypothesis] = None
    contributing_causes: list[CauseHypothesis] = field(default_factory=list)
    overall_status: CausalStatus = CausalStatus.UNKNOWN
    conclusion: str = ""
    evidence_refs: list[str] = field(default_factory=list)
    gap_refs: list[str] = field(default_factory=list)
    strategy_ref: Optional[str] = None
    experiment_ref: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    # lifecycle evidence hints only — does NOT auto-transition
    lifecycle_evidence_hint: Optional[str] = None  # e.g. DEGRADED_CANDIDATE
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "failure_id": self.failure_id,
            "timestamp": self.timestamp,
            "primary_candidate": (
                self.primary_candidate.to_dict() if self.primary_candidate else None
            ),
            "contributing_causes": [c.to_dict() for c in self.contributing_causes],
            "overall_status": self.overall_status.value,
            "conclusion": self.conclusion,
            "evidence_refs": list(self.evidence_refs),
            "gap_refs": list(self.gap_refs),
            "strategy_ref": self.strategy_ref,
            "experiment_ref": self.experiment_ref,
            "provenance": dict(self.provenance) if self.provenance else None,
            "lifecycle_evidence_hint": self.lifecycle_evidence_hint,
            "metadata": dict(self.metadata),
        }


def make_failure_id(
    source: str,
    strategy_ref: Optional[str],
    experiment_ref: Optional[str],
    expected: Optional[str],
    observed: Optional[str],
) -> str:
    payload = {
        "src": source,
        "s": strategy_ref or "",
        "e": experiment_ref or "",
        "exp": expected or "",
        "obs": observed or "",
    }
    return "fail-" + content_hash(payload)[:24]


def make_assessment_id(failure_id: str, evidence_key: str) -> str:
    return "rca-" + content_hash({"f": failure_id, "ev": evidence_key})[:24]
