"""Cognitive operational health for N.U.N.G. — not trading readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from .models import ControlState


@dataclass
class CognitiveHealth:
    control_state: ControlState = ControlState.STOPPED
    cognitive_label: str = "COGNITIVE_PAUSED"
    last_successful_cycle: Optional[str] = None
    last_failed_cycle: Optional[str] = None
    current_cycle: Optional[str] = None
    last_correlation_id: Optional[str] = None
    last_snapshot_id: Optional[str] = None
    ledger_records: int = 0
    corruption_flag: bool = False
    pause_requested: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "control_state": self.control_state.value,
            "cognitive_label": self.cognitive_label,
            "last_successful_cycle": self.last_successful_cycle,
            "last_failed_cycle": self.last_failed_cycle,
            "current_cycle": self.current_cycle,
            "last_correlation_id": self.last_correlation_id,
            "last_snapshot_id": self.last_snapshot_id,
            "ledger_records": self.ledger_records,
            "corruption_flag": self.corruption_flag,
            "pause_requested": self.pause_requested,
            "notes": self.notes,
        }


def label_for_state(state: ControlState) -> str:
    return {
        ControlState.STOPPED: "COGNITIVE_STOPPED",
        ControlState.READY: "COGNITIVE_READY",
        ControlState.RUNNING: "COGNITIVE_RUNNING",
        ControlState.PAUSED: "COGNITIVE_PAUSED",
        ControlState.DEGRADED: "COGNITIVE_DEGRADED",
        ControlState.CORRUPTED: "COGNITIVE_CORRUPTED",
    }.get(state, "COGNITIVE_UNKNOWN")
