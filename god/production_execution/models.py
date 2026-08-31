"""Phase 6G — N.U.N.G. production execution models. Authorization-gated."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Protocol

from god.research.provenance import content_hash


class ExecutionMode(str, Enum):
    PAPER = "PAPER"
    SHADOW = "SHADOW"
    LIVE = "LIVE"


class ExecutionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SIMULATED = "SIMULATED"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"


class ReconciliationState(str, Enum):
    CONSISTENT = "CONSISTENT"
    PENDING = "PENDING"
    MISMATCHED = "MISMATCHED"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"
    REJECTED = "REJECTED"


class ProviderHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"
    CORRUPTED = "CORRUPTED"
    UNKNOWN = "UNKNOWN"


SCHEMA_VERSION = "production-execution-6g-v1"


@dataclass(frozen=True)
class ProductionExecutionRequest:
    request_id: str
    intent_id: str
    decision_id: str
    symbol: str
    action: str
    execution_mode: ExecutionMode
    environment: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    strategy_ref: str = ""
    observation_ts: str = ""
    created_at: str = ""
    authorization_id: str = ""
    correlation_id: str = ""
    risk_id: str = ""
    provenance: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "intent_id": self.intent_id,
            "decision_id": self.decision_id,
            "symbol": self.symbol,
            "action": self.action,
            "execution_mode": self.execution_mode.value,
            "environment": self.environment,
            "strategy_ref": self.strategy_ref,
            "observation_ts": self.observation_ts,
            "created_at": self.created_at,
            "authorization_id": self.authorization_id,
            "correlation_id": self.correlation_id,
            "risk_id": self.risk_id,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "provenance": dict(self.provenance) if self.provenance else None,
        }


@dataclass(frozen=True)
class ProductionExecutionResult:
    request_id: str
    execution_id: str
    status: ExecutionStatus
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    provider_ref: str = ""
    simulated: bool = True
    reconciliation: ReconciliationState = ReconciliationState.UNKNOWN
    error_class: str = ""
    timestamp: str = ""
    provenance: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "execution_id": self.execution_id,
            "status": self.status.value,
            "provider_ref": self.provider_ref,
            "simulated": self.simulated,
            "reconciliation": self.reconciliation.value,
            "error_class": self.error_class,
            "timestamp": self.timestamp,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
            "provenance": dict(self.provenance) if self.provenance else None,
        }


def make_request_id(payload: dict[str, Any]) -> str:
    return "pexreq-" + content_hash(payload)[:24]


def make_execution_id(payload: dict[str, Any]) -> str:
    return "pex-" + content_hash(payload)[:24]


class ProductionExecutionProvider(Protocol):
    def submit(self, request: ProductionExecutionRequest) -> ProductionExecutionResult: ...

    def health(self) -> ProviderHealth: ...
