"""Phase 5E — N.U.N.G. paper risk models. Simulation only."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash

from .models import build_paper_provenance


class RiskLevel(str, Enum):
    NORMAL = "NORMAL"
    WARNING = "WARNING"
    BLOCKED = "BLOCKED"


class SafetyDecision(str, Enum):
    PAPER_ALLOWED = "PAPER_ALLOWED"
    BLOCKED = "BLOCKED"


class RiskStatus(str, Enum):
    VALID = "VALID"
    UNKNOWN = "UNKNOWN"
    STALE = "STALE"
    INVALID = "INVALID"
    CORRUPTED = "CORRUPTED"
    MISSING_DATA = "MISSING_DATA"
    FAILED = "FAILED"


SCHEMA_VERSION = "paper-risk-5e-v1"


@dataclass(frozen=True)
class PaperRiskAssessment:
    risk_id: str
    decision: SafetyDecision
    risk_level: RiskLevel
    risk_status: RiskStatus
    content_hash: str
    reason_codes: tuple[str, ...] = ()
    drawdown: Optional[float] = None
    decision_id: Optional[str] = None
    cycle_id: Optional[str] = None
    schema_version: str = SCHEMA_VERSION
    provenance: Optional[dict[str, Any]] = None
    notes: str = "paper_risk_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_id": self.risk_id,
            "decision": self.decision.value,
            "risk_level": self.risk_level.value,
            "risk_status": self.risk_status.value,
            "content_hash": self.content_hash,
            "reason_codes": list(self.reason_codes),
            "drawdown": self.drawdown,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "schema_version": self.schema_version,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


def make_risk_id(payload: dict[str, Any]) -> str:
    return "risk-" + content_hash(payload)[:24]
