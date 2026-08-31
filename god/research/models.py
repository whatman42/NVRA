"""Typed research-layer models — fact / claim / hypothesis separation.

Nothing here is a trading rule. Confidence scores are descriptive assessments
of evidence quality, not execution gates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ClaimStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    UNDER_REVIEW = "UNDER_REVIEW"
    SUPPORTED = "SUPPORTED"
    DISPUTED = "DISPUTED"
    RETRACTED = "RETRACTED"
    POISONED = "POISONED"


class HypothesisStatus(str, Enum):
    PROPOSED = "PROPOSED"
    TESTING = "TESTING"
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    RETIRED = "RETIRED"


class ExperimentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class ExperimentOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    ERROR = "ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"


class SourceReliability(str, Enum):
    UNKNOWN = "UNKNOWN"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True)
class FactRecord:
    """Observable, checkable statement with provenance (not a belief)."""

    fact_id: str
    statement: str
    observed_at: str
    provenance_id: Optional[str] = None
    content_hash: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_id": self.fact_id,
            "statement": self.statement,
            "observed_at": self.observed_at,
            "provenance_id": self.provenance_id,
            "content_hash": self.content_hash,
            "metadata": dict(self.metadata),
        }


@dataclass
class EvidenceRecord:
    """Link between data/facts and a claim under evaluation."""

    evidence_id: str
    claim_id: str
    summary: str
    fact_ids: list[str] = field(default_factory=list)
    weight: float = 1.0  # relative descriptive weight — not a trading threshold
    methodology: Optional[str] = None
    limitations: Optional[str] = None
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "claim_id": self.claim_id,
            "summary": self.summary,
            "fact_ids": list(self.fact_ids),
            "weight": self.weight,
            "methodology": self.methodology,
            "limitations": self.limitations,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }


@dataclass
class ProvenanceRecord:
    provenance_id: str
    source_id: Optional[str]
    origin: str  # e.g. url, file path label, "synthetic", "observation"
    retrieved_at: str
    content_hash: str
    raw_ref: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provenance_id": self.provenance_id,
            "source_id": self.source_id,
            "origin": self.origin,
            "retrieved_at": self.retrieved_at,
            "content_hash": self.content_hash,
            "raw_ref": self.raw_ref,
            "metadata": dict(self.metadata),
        }


@dataclass
class SourceProfile:
    source_id: str
    name: str
    reliability: SourceReliability = SourceReliability.UNKNOWN
    success_count: int = 0
    failure_count: int = 0
    anomaly_count: int = 0
    last_seen: Optional[str] = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "reliability": self.reliability.value,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "anomaly_count": self.anomaly_count,
            "last_seen": self.last_seen,
            "metadata": dict(self.metadata),
        }


@dataclass
class AssessmentResult:
    """Descriptive evidence quality — not an execution unlock."""

    claim_id: str
    score: float  # 0..1 descriptive
    supporting: int = 0
    contradicting: int = 0
    source_reliability: SourceReliability = SourceReliability.UNKNOWN
    notes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "score": self.score,
            "supporting": self.supporting,
            "contradicting": self.contradicting,
            "source_reliability": self.source_reliability.value,
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }


@dataclass
class ResearchEvent:
    event_type: str
    entity_type: str
    entity_id: str
    detail: dict = field(default_factory=dict)
    timestamp: str = ""
