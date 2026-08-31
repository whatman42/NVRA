"""Phase 4H — Discovery models. Descriptive only. No execution authority."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class InstrumentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INVALID_DATA = "INVALID_DATA"
    STALE = "STALE"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"
    ELIGIBLE = "ELIGIBLE"
    INELIGIBLE = "INELIGIBLE"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    INELIGIBLE = "INELIGIBLE"
    UNKNOWN = "UNKNOWN"


class DiscoveryStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    ELIGIBLE = "ELIGIBLE"
    RESTRICTED = "RESTRICTED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NO_VALID_CANDIDATE = "NO_VALID_CANDIDATE"
    UNKNOWN = "UNKNOWN"


class QualityStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class InstrumentRef:
    symbol: str
    asset_class: str = "UNKNOWN"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "asset_class": self.asset_class,
            "metadata": dict(self.metadata),
        }


@dataclass
class Candidate:
    """Discovery candidate — not an order."""

    candidate_id: str
    instrument_ref: str
    strategy_ref: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    research_refs: list[str] = field(default_factory=list)
    validation_refs: list[str] = field(default_factory=list)
    drift_refs: list[str] = field(default_factory=list)
    regime_refs: list[str] = field(default_factory=list)
    policy_refs: list[str] = field(default_factory=list)
    capital_refs: list[str] = field(default_factory=list)
    quality_status: QualityStatus = QualityStatus.UNKNOWN
    eligibility: EligibilityStatus = EligibilityStatus.UNKNOWN
    uncertainty: str = "UNKNOWN"
    confidence_desc: Optional[str] = None  # descriptive only, not execution gate
    ranking_metadata: dict[str, Any] = field(default_factory=dict)
    provenance: Optional[dict[str, Any]] = None
    content_hash: Optional[str] = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "instrument_ref": self.instrument_ref,
            "strategy_ref": self.strategy_ref,
            "evidence_refs": list(self.evidence_refs),
            "research_refs": list(self.research_refs),
            "validation_refs": list(self.validation_refs),
            "drift_refs": list(self.drift_refs),
            "regime_refs": list(self.regime_refs),
            "policy_refs": list(self.policy_refs),
            "capital_refs": list(self.capital_refs),
            "quality_status": self.quality_status.value,
            "eligibility": self.eligibility.value,
            "uncertainty": self.uncertainty,
            "confidence_desc": self.confidence_desc,
            "ranking_metadata": dict(self.ranking_metadata),
            "provenance": dict(self.provenance) if self.provenance else None,
            "content_hash": self.content_hash,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


@dataclass
class DiscoveryResult:
    result_id: str
    status: DiscoveryStatus
    universe_size: int = 0
    analyzed_count: int = 0
    eligible_candidates: list[Candidate] = field(default_factory=list)
    restricted_candidates: list[Candidate] = field(default_factory=list)
    blocked_candidates: list[Candidate] = field(default_factory=list)
    insufficient_data: list[str] = field(default_factory=list)
    ranking: list[str] = field(default_factory=list)  # candidate_ids in rank order
    evidence_refs: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    discovery_version: str = "discovery-4h-v1"
    timestamp: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "status": self.status.value,
            "universe_size": self.universe_size,
            "analyzed_count": self.analyzed_count,
            "eligible_candidates": [c.to_dict() for c in self.eligible_candidates],
            "restricted_candidates": [c.to_dict() for c in self.restricted_candidates],
            "blocked_candidates": [c.to_dict() for c in self.blocked_candidates],
            "insufficient_data": list(self.insufficient_data),
            "ranking": list(self.ranking),
            "evidence_refs": list(self.evidence_refs),
            "provenance": dict(self.provenance) if self.provenance else None,
            "discovery_version": self.discovery_version,
            "timestamp": self.timestamp,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


def make_candidate_id(
    instrument: str,
    strategy_ref: Optional[str],
    evidence_key: str,
) -> str:
    return "cand-" + content_hash(
        {"i": instrument, "s": strategy_ref or "", "e": evidence_key}
    )[:24]


def make_result_id(
    universe_key: str,
    discovery_version: str,
    fingerprint: str,
) -> str:
    return "disc-" + content_hash(
        {"u": universe_key, "v": discovery_version, "f": fingerprint}
    )[:24]
