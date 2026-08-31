"""Phase 4P — N.U.N.G. shadow decision models. Cognitive only. No orders."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance_dict, content_hash


class ValidityState(str, Enum):
    VALID = "VALID"
    STALE = "STALE"
    INVALID = "INVALID"
    UNKNOWN = "UNKNOWN"
    CORRUPTED = "CORRUPTED"


class ShadowStatus(str, Enum):
    SELECTED = "SELECTED"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NO_VALID_OPPORTUNITY = "NO_VALID_OPPORTUNITY"
    STILL_VALID = "STILL_VALID"
    NO_LONGER_VALID = "NO_LONGER_VALID"


@dataclass(frozen=True)
class DecisionConfig:
    max_decisions: int = 200
    max_revisions_per_decision: int = 20
    max_triggers: int = 100
    max_evidence_refs: int = 50
    decision_ttl_seconds: Optional[float] = None  # None = no TTL
    schema_version: str = "decision-4p-v1"


@dataclass
class ShadowDecision:
    decision_id: str
    cycle_id: str
    correlation_id: str
    status: ShadowStatus
    validity: ValidityState
    revision: int
    content_hash: str
    created_at: str
    opportunity_id: Optional[str] = None
    symbol: Optional[str] = None
    strategy_ref: Optional[str] = None
    policy_status: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    evidence_fingerprint: str = ""
    parent_decision_id: Optional[str] = None
    parent_revision: Optional[int] = None
    valid_until: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    reason_codes: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "validity": self.validity.value,
            "revision": self.revision,
            "content_hash": self.content_hash,
            "created_at": self.created_at,
            "opportunity_id": self.opportunity_id,
            "symbol": self.symbol,
            "strategy_ref": self.strategy_ref,
            "policy_status": self.policy_status,
            "evidence_refs": list(self.evidence_refs),
            "evidence_fingerprint": self.evidence_fingerprint,
            "parent_decision_id": self.parent_decision_id,
            "parent_revision": self.parent_revision,
            "valid_until": self.valid_until,
            "provenance": dict(self.provenance) if self.provenance else None,
            "reason_codes": list(self.reason_codes),
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }


def make_decision_id(
    cycle_id: str,
    opportunity_id: Optional[str],
    evidence_fp: str,
    status: str,
    revision: int,
    version: str = "decision-4p-v1",
) -> str:
    return "dec-" + content_hash(
        {
            "c": cycle_id,
            "o": opportunity_id or "",
            "e": evidence_fp,
            "s": status,
            "r": revision,
            "v": version,
        }
    )[:24]


def evidence_fingerprint(refs: list[str], extra: Optional[dict[str, Any]] = None) -> str:
    return content_hash({"refs": sorted(refs), "x": extra or {}})


def build_decision_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="decision_4p", payload=payload)


def decision_content_hash(payload: dict[str, Any]) -> str:
    return content_hash(payload)
