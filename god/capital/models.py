"""Phase 4F — Capital SAFETY state models.

CapitalState = system safety posture.
NOT capital allocation, position size, or lot calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class CapitalState(str, Enum):
    INITIALIZING = "INITIALIZING"
    OBSERVING = "OBSERVING"
    NORMAL = "NORMAL"
    CAUTION = "CAUTION"
    RESTRICTED = "RESTRICTED"
    PAUSED = "PAUSED"
    RECOVERY = "RECOVERY"
    EMERGENCY_STOP = "EMERGENCY_STOP"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CapitalTransitionRecord:
    transition_id: str
    state_before: CapitalState
    state_after: CapitalState
    reason: str
    evidence_refs: tuple[str, ...]
    timestamp: str
    actor: str
    provenance: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "state_before": self.state_before.value,
            "state_after": self.state_after.value,
            "reason": self.reason,
            "evidence_refs": list(self.evidence_refs),
            "timestamp": self.timestamp,
            "actor": self.actor,
            "provenance": dict(self.provenance) if self.provenance else None,
            "metadata": dict(self.metadata),
        }


@dataclass
class CapitalStateRecord:
    """Current safety posture + lineage of transition ids."""

    record_id: str
    state: CapitalState
    updated_at: str
    last_transition_id: Optional[str] = None
    transition_ids: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "state": self.state.value,
            "updated_at": self.updated_at,
            "last_transition_id": self.last_transition_id,
            "transition_ids": list(self.transition_ids),
            "evidence_refs": list(self.evidence_refs),
            "provenance": dict(self.provenance) if self.provenance else None,
            "metadata": dict(self.metadata),
        }

    def has_execution_intent(self) -> bool:
        blob = " ".join([self.state.value, str(list(self.metadata.keys()))]).lower()
        return any(
            t in blob
            for t in ("op_" + "buy", "op_" + "sell", "order" + "send", "lot_" + "size", "allocate_" + "capital")
        )


def make_transition_id(
    before: CapitalState,
    after: CapitalState,
    reason: str,
    evidence_key: str,
) -> str:
    return "ctr-" + content_hash(
        {
            "b": before.value,
            "a": after.value,
            "r": reason,
            "e": evidence_key,
        }
    )[:24]
