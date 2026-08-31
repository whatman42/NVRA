"""Phase 5A — N.U.N.G. execution contract models. No live trading."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.research.provenance import build_provenance_dict, content_hash


class IntentAction(str, Enum):
    NO_ACTION = "NO_ACTION"
    PAPER_ENTER = "PAPER_ENTER"
    PAPER_EXIT = "PAPER_EXIT"


class IntentStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    STALE = "STALE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"
    CORRUPTED = "CORRUPTED"


class ResultStatus(str, Enum):
    NULL_EXECUTED = "NULL_EXECUTED"
    SIMULATED = "SIMULATED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


SCHEMA_VERSION = "execution-contract-5a-v1"


@dataclass(frozen=True)
class ExecutionIntent:
    intent_id: str
    decision_id: str
    cycle_id: str
    opportunity_id: str
    symbol: str
    strategy_ref: Optional[str]
    decision_status: str
    intent_action: IntentAction
    intent_status: IntentStatus
    created_at: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    valid_until: Optional[str] = None
    evidence_refs: tuple[str, ...] = ()
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "opportunity_id": self.opportunity_id,
            "symbol": self.symbol,
            "strategy_ref": self.strategy_ref,
            "decision_status": self.decision_status,
            "intent_action": self.intent_action.value,
            "intent_status": self.intent_status.value,
            "created_at": self.created_at,
            "valid_until": self.valid_until,
            "evidence_refs": list(self.evidence_refs),
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ExecutionResult:
    result_id: str
    intent_id: str
    decision_id: str
    cycle_id: str
    status: ResultStatus
    provider: str
    executed: bool
    simulated: bool
    created_at: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    reason_codes: tuple[str, ...] = ()
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "status": self.status.value,
            "provider": self.provider,
            "executed": self.executed,
            "simulated": self.simulated,
            "created_at": self.created_at,
            "reason_codes": list(self.reason_codes),
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


def make_intent_id(payload: dict[str, Any]) -> str:
    return "intent-" + content_hash(payload)[:24]


def make_result_id(payload: dict[str, Any]) -> str:
    return "eres-" + content_hash(payload)[:24]


def build_exec_provenance(payload: dict[str, Any]) -> dict[str, Any]:
    return build_provenance_dict(origin="execution_contract_5a", payload=payload)
