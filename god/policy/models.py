"""Phase 4F — Policy models.

Permission = safety gate only. NOT BUY/SELL/OPEN/CLOSE.
PolicyDecision is SAFETY KNOWLEDGE, not trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class Permission(str, Enum):
    """Safety permissions only — never mapped to OPEN/BUY/SELL."""

    ALLOW = "ALLOW"
    RESTRICT = "RESTRICT"
    PAUSE = "PAUSE"
    BLOCK = "BLOCK"
    UNKNOWN = "UNKNOWN"


class HealthFlag(str, Enum):
    """Injected health — descriptive, not broker calls."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class PolicyEvidenceBundle:
    """Typed evidence container. No order instructions. No credentials."""

    system_health: HealthFlag = HealthFlag.UNKNOWN
    data_quality: str = "UNKNOWN"  # e.g. VALID / INVALID / INSUFFICIENT_DATA
    bridge_health: HealthFlag = HealthFlag.UNKNOWN
    execution_health: HealthFlag = HealthFlag.UNKNOWN
    reality_gap_refs: list[str] = field(default_factory=list)
    rca_refs: list[str] = field(default_factory=list)
    drift_refs: list[str] = field(default_factory=list)
    regime_refs: list[str] = field(default_factory=list)
    strategy_lifecycle_state: Optional[str] = None  # e.g. RETIRED, DEGRADED
    uncertainty: str = "UNKNOWN"
    evidence_refs: list[str] = field(default_factory=list)
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: Optional[dict[str, Any]] = None

    def fingerprint(self) -> str:
        payload = {
            "system": self.system_health.value,
            "data": self.data_quality,
            "bridge": self.bridge_health.value,
            "exec": self.execution_health.value,
            "rg": sorted(self.reality_gap_refs),
            "rca": sorted(self.rca_refs),
            "drift": sorted(self.drift_refs),
            "regime": sorted(self.regime_refs),
            "sls": self.strategy_lifecycle_state or "",
            "unc": self.uncertainty,
            "ev": sorted(self.evidence_refs),
        }
        return content_hash(payload)

    def has_execution_intent(self) -> bool:
        blob = " ".join(
            [
                self.notes,
                str(list(self.metadata.keys())),
                self.strategy_lifecycle_state or "",
            ]
        ).lower()
        return any(
            t in blob
            for t in (
                "op_" + "buy",
                "op_" + "sell",
                "order" + "send",
                "lot_" + "size",
                "allocate_" + "capital",
                "side=" + "buy",
                "side=" + "sell",
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "system_health": self.system_health.value,
            "data_quality": self.data_quality,
            "bridge_health": self.bridge_health.value,
            "execution_health": self.execution_health.value,
            "reality_gap_refs": list(self.reality_gap_refs),
            "rca_refs": list(self.rca_refs),
            "drift_refs": list(self.drift_refs),
            "regime_refs": list(self.regime_refs),
            "strategy_lifecycle_state": self.strategy_lifecycle_state,
            "uncertainty": self.uncertainty,
            "evidence_refs": list(self.evidence_refs),
            "notes": self.notes,
            "metadata": dict(self.metadata),
            "provenance": dict(self.provenance) if self.provenance else None,
        }


@dataclass
class PolicyDecision:
    decision_id: str
    permission: Permission
    reasons: list[str]
    evidence_refs: list[str]
    uncertainty: str
    policy_version: str
    composition_trace: list[str]
    provenance: Optional[dict[str, Any]]
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision_id": self.decision_id,
            "permission": self.permission.value,
            "reasons": list(self.reasons),
            "evidence_refs": list(self.evidence_refs),
            "uncertainty": self.uncertainty,
            "policy_version": self.policy_version,
            "composition_trace": list(self.composition_trace),
            "provenance": dict(self.provenance) if self.provenance else None,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    def has_execution_intent(self) -> bool:
        blob = " ".join(self.reasons + self.composition_trace).lower()
        markers = [
            "op_" + "buy",
            "op_" + "sell",
            "order" + "send",
            "open " + "position",
            "place " + "order",
        ]
        return any(t in blob for t in markers)


def make_decision_id(fingerprint: str, policy_version: str) -> str:
    return "pol-" + content_hash({"fp": fingerprint, "pv": policy_version})[:24]
