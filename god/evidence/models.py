"""Typed models for Evidence Registry and ReviewArtifact.

All timestamps are UTC ISO-8601 strings.
Artifacts are designed to be JSON-serializable and append-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List, Dict
import uuid
import json
from datetime import datetime, timezone


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EvidenceGrade(str, Enum):
    """Epistemic status — not a quality score."""
    E0 = "E0"  # unsupported claim / assumption
    E1 = "E1"  # static / code inspection
    E2 = "E2"  # unit / contract test
    E3 = "E3"  # integration evidence
    E4 = "E4"  # controlled simulation
    E5 = "E5"  # historical / out-of-sample
    E6 = "E6"  # realistic execution / environment
    E7 = "E7"  # production-environment evidence


class ImpactDomain(str, Enum):
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    MEMORY = "memory"
    DATA = "data"
    RESEARCH = "research"
    QUANT = "quant"
    ML = "ml"
    EXECUTION = "execution"
    ACCOUNTING = "accounting"
    BRIDGE = "bridge"
    EA = "ea"
    WINDOWS = "windows"
    SECURITY = "security"
    PACKAGING = "packaging"
    DEPLOYMENT = "deployment"
    REPOSITORY = "repository"
    FAULT_RECOVERY = "fault_recovery"


class PromotionState(str, Enum):
    RESEARCH_ONLY = "RESEARCH_ONLY"
    UNDER_REVIEW = "UNDER_REVIEW"
    ACCEPTED = "ACCEPTED"
    PROMOTION_CANDIDATE = "PROMOTION_CANDIDATE"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    ROLLED_BACK = "ROLLED_BACK"


class ReviewDecision(str, Enum):
    ACCEPT = "ACCEPT"
    ACCEPT_WITH_UNCERTAINTY = "ACCEPT_WITH_UNCERTAINTY"
    REJECT = "REJECT"
    ROLLBACK = "ROLLBACK"
    RESEARCH_ONLY = "RESEARCH_ONLY"


class ReviewerMode(str, Enum):
    INDEPENDENT = "Independent"
    ADVERSARIAL = "Adversarial"
    BUILDER = "Builder"  # should never be used for promotion decisions


@dataclass
class EvidenceClaim:
    """A single claim about a domain with its supporting evidence grade."""
    domain: ImpactDomain
    grade: EvidenceGrade
    claim: str
    evidence_refs: List[str] = field(default_factory=list)
    environment: str = "unknown"
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "domain": self.domain.value,
            "grade": self.grade.value,
            "claim": self.claim,
            "evidence_refs": list(self.evidence_refs),
            "environment": self.environment,
            "notes": self.notes,
        }

    @staticmethod
    def from_dict(d: dict) -> "EvidenceClaim":
        return EvidenceClaim(
            domain=ImpactDomain(d["domain"]),
            grade=EvidenceGrade(d["grade"]),
            claim=d["claim"],
            evidence_refs=list(d.get("evidence_refs") or []),
            environment=d.get("environment", "unknown"),
            notes=d.get("notes", ""),
        )


@dataclass
class ReviewArtifact:
    """Immutable (semantically) record of an Independent Review.

    Corrections create a new artifact with parent_artifact_id set.
    """
    artifact_id: str
    repository: str
    commit_sha: str
    timestamp: str
    reviewer_mode: ReviewerMode
    impact_classification: List[ImpactDomain]
    evidence_claims: List[EvidenceClaim]
    decision: ReviewDecision
    promotion_state: PromotionState
    remaining_uncertainty: str
    anomalies: List[str] = field(default_factory=list)
    tests_executed: List[str] = field(default_factory=list)
    test_results_summary: Dict[str, Any] = field(default_factory=dict)
    environment_fingerprint: Dict[str, str] = field(default_factory=dict)
    parent_artifact_id: Optional[str] = None
    change_summary: str = ""
    validation_method: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def create(
        repository: str,
        commit_sha: str,
        reviewer_mode: ReviewerMode,
        impact_classification: List[ImpactDomain],
        evidence_claims: List[EvidenceClaim],
        decision: ReviewDecision,
        promotion_state: PromotionState,
        remaining_uncertainty: str,
        **kw: Any,
    ) -> "ReviewArtifact":
        return ReviewArtifact(
            artifact_id=kw.get("artifact_id") or new_id(),
            repository=repository,
            commit_sha=commit_sha,
            timestamp=kw.get("timestamp") or utc_now_iso(),
            reviewer_mode=reviewer_mode,
            impact_classification=list(impact_classification),
            evidence_claims=list(evidence_claims),
            decision=decision,
            promotion_state=promotion_state,
            remaining_uncertainty=remaining_uncertainty,
            anomalies=list(kw.get("anomalies") or []),
            tests_executed=list(kw.get("tests_executed") or []),
            test_results_summary=dict(kw.get("test_results_summary") or {}),
            environment_fingerprint=dict(kw.get("environment_fingerprint") or {}),
            parent_artifact_id=kw.get("parent_artifact_id"),
            change_summary=kw.get("change_summary", ""),
            validation_method=kw.get("validation_method", ""),
            metadata=dict(kw.get("metadata") or {}),
        )

    def to_dict(self) -> dict:
        return {
            "artifact_id": self.artifact_id,
            "repository": self.repository,
            "commit_sha": self.commit_sha,
            "timestamp": self.timestamp,
            "reviewer_mode": self.reviewer_mode.value,
            "impact_classification": [d.value for d in self.impact_classification],
            "evidence_claims": [c.to_dict() for c in self.evidence_claims],
            "decision": self.decision.value,
            "promotion_state": self.promotion_state.value,
            "remaining_uncertainty": self.remaining_uncertainty,
            "anomalies": list(self.anomalies),
            "tests_executed": list(self.tests_executed),
            "test_results_summary": dict(self.test_results_summary),
            "environment_fingerprint": dict(self.environment_fingerprint),
            "parent_artifact_id": self.parent_artifact_id,
            "change_summary": self.change_summary,
            "validation_method": self.validation_method,
            "metadata": dict(self.metadata),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    @staticmethod
    def from_dict(d: dict) -> "ReviewArtifact":
        return ReviewArtifact(
            artifact_id=d["artifact_id"],
            repository=d["repository"],
            commit_sha=d["commit_sha"],
            timestamp=d["timestamp"],
            reviewer_mode=ReviewerMode(d["reviewer_mode"]),
            impact_classification=[ImpactDomain(x) for x in d.get("impact_classification") or []],
            evidence_claims=[EvidenceClaim.from_dict(c) for c in d.get("evidence_claims") or []],
            decision=ReviewDecision(d["decision"]),
            promotion_state=PromotionState(d["promotion_state"]),
            remaining_uncertainty=d.get("remaining_uncertainty", ""),
            anomalies=list(d.get("anomalies") or []),
            tests_executed=list(d.get("tests_executed") or []),
            test_results_summary=dict(d.get("test_results_summary") or {}),
            environment_fingerprint=dict(d.get("environment_fingerprint") or {}),
            parent_artifact_id=d.get("parent_artifact_id"),
            change_summary=d.get("change_summary", ""),
            validation_method=d.get("validation_method", ""),
            metadata=dict(d.get("metadata") or {}),
        )
