"""CognitiveContext — lifecycle state for orchestration loops."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class CognitiveStage(str, Enum):
    CURIOSITY = "CURIOSITY"
    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT = "EXPERIMENT"
    VALIDATION = "VALIDATION"
    STRATEGY = "STRATEGY"
    REALITY_GAP = "REALITY_GAP"
    RCA = "RCA"
    DRIFT = "DRIFT"
    REGIME = "REGIME"
    POLICY = "POLICY"
    CAPITAL_SAFETY = "CAPITAL_SAFETY"
    COMPLETE = "COMPLETE"


class ContextStatus(str, Enum):
    START = "START"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    RESUME = "RESUME"
    FAILED = "FAILED"
    CORRUPTED = "CORRUPTED"
    CANCELLED = "CANCELLED"
    COMPLETE = "COMPLETE"


FORBIDDEN_CONTEXT_STATUS = frozenset()  # reserved; status validation lives in transitions


_ALLOWED_TRANSITIONS: dict[ContextStatus, frozenset[ContextStatus]] = {
    ContextStatus.START: frozenset({ContextStatus.RUNNING, ContextStatus.CANCELLED}),
    ContextStatus.RUNNING: frozenset(
        {
            ContextStatus.PAUSED,
            ContextStatus.FAILED,
            ContextStatus.CORRUPTED,
            ContextStatus.COMPLETE,
            ContextStatus.CANCELLED,
        }
    ),
    ContextStatus.PAUSED: frozenset({ContextStatus.RESUME, ContextStatus.CANCELLED}),
    ContextStatus.RESUME: frozenset({ContextStatus.RUNNING, ContextStatus.CANCELLED}),
    ContextStatus.FAILED: frozenset({ContextStatus.CANCELLED}),
    ContextStatus.CORRUPTED: frozenset({ContextStatus.CANCELLED}),
    ContextStatus.CANCELLED: frozenset(),
    ContextStatus.COMPLETE: frozenset(),
}


def assert_status_transition(from_status: ContextStatus, to_status: ContextStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise ValueError(f"illegal status transition {from_status.value} -> {to_status.value}")


@dataclass
class CognitiveContext:
    context_id: str
    correlation_id: str
    status: ContextStatus = ContextStatus.START
    current_stage: CognitiveStage = CognitiveStage.CURIOSITY
    completed_nodes: list[str] = field(default_factory=list)
    evidence_index: dict[str, str] = field(default_factory=dict)
    checkpoint_reference: Optional[str] = None
    attempt_count: int = 0
    updated_at: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "context_id": self.context_id,
            "correlation_id": self.correlation_id,
            "status": self.status.value,
            "current_stage": self.current_stage.value,
            "completed_nodes": list(self.completed_nodes),
            "evidence_index": dict(self.evidence_index),
            "checkpoint_reference": self.checkpoint_reference,
            "attempt_count": self.attempt_count,
            "updated_at": self.updated_at,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CognitiveContext":
        return cls(
            context_id=str(d["context_id"]),
            correlation_id=str(d.get("correlation_id") or d["context_id"]),
            status=ContextStatus(d.get("status") or "START"),
            current_stage=CognitiveStage(d.get("current_stage") or "CURIOSITY"),
            completed_nodes=list(d.get("completed_nodes") or []),
            evidence_index=dict(d.get("evidence_index") or {}),
            checkpoint_reference=d.get("checkpoint_reference"),
            attempt_count=int(d.get("attempt_count") or 0),
            updated_at=str(d.get("updated_at") or ""),
            created_at=str(d.get("created_at") or ""),
        )


def create_context(
    *,
    correlation_id: str,
    context_id: Optional[str] = None,
    stage: CognitiveStage = CognitiveStage.CURIOSITY,
    created_at: str = "",
) -> CognitiveContext:
    if context_id is None:
        context_id = "ctx-" + hashlib.sha256(correlation_id.encode()).hexdigest()[:16]
    return CognitiveContext(
        context_id=context_id,
        correlation_id=correlation_id,
        current_stage=stage,
        created_at=created_at,
        updated_at=created_at,
    )
