"""Phase 5B — N.U.N.G. paper execution models. Simulation only."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.research.provenance import build_provenance_dict, content_hash


class PaperStatus(str, Enum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    PAPER_SIMULATED = "PAPER_SIMULATED"
    PAPER_REJECTED = "PAPER_REJECTED"
    PAPER_FAILED = "PAPER_FAILED"


SCHEMA_VERSION = "paper-5b-v1"


@dataclass(frozen=True)
class PaperFill:
    fill_id: str
    paper_execution_id: str
    symbol: str
    reference_price: Optional[float]
    simulated_at: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    source_snapshot_id: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    notes: str = "simulated_fill_not_broker"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "paper_execution_id": self.paper_execution_id,
            "symbol": self.symbol,
            "reference_price": self.reference_price,
            "simulated_at": self.simulated_at,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "source_snapshot_id": self.source_snapshot_id,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class PaperExecution:
    paper_execution_id: str
    intent_id: str
    decision_id: str
    cycle_id: str
    symbol: str
    action: str
    status: PaperStatus
    simulated_at: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    fill: Optional[PaperFill] = None
    provenance: Optional[dict[str, Any]] = None
    reason_codes: tuple[str, ...] = ()
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "paper_execution_id": self.paper_execution_id,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "symbol": self.symbol,
            "action": self.action,
            "status": self.status.value,
            "simulated_at": self.simulated_at,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "fill": self.fill.to_dict() if self.fill else None,
            "provenance": dict(self.provenance) if self.provenance else None,
            "reason_codes": list(self.reason_codes),
            "notes": self.notes,
        }


def make_paper_id(payload: dict[str, Any]) -> str:
    return "paper-" + content_hash(payload)[:24]


def make_fill_id(payload: dict[str, Any]) -> str:
    return "pfill-" + content_hash(payload)[:24]


def build_paper_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="paper_5b", payload=payload)
