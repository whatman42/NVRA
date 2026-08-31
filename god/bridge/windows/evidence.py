"""EA load evidence ladder — file presence ≠ active EA."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class LoadEvidenceLevel(str, Enum):
    NONE = "NONE"
    FILE_PRESENT = "FILE_PRESENT"
    COMPILE_VALID = "COMPILE_VALID"
    TERMINAL_DETECTED = "TERMINAL_DETECTED"
    EA_HELLO_RECEIVED = "EA_HELLO_RECEIVED"
    HEARTBEAT_RECEIVED = "HEARTBEAT_RECEIVED"
    RECONCILIATION_OK = "RECONCILIATION_OK"
    READY = "READY"


_LADDER = [
    LoadEvidenceLevel.FILE_PRESENT,
    LoadEvidenceLevel.COMPILE_VALID,
    LoadEvidenceLevel.TERMINAL_DETECTED,
    LoadEvidenceLevel.EA_HELLO_RECEIVED,
    LoadEvidenceLevel.HEARTBEAT_RECEIVED,
    LoadEvidenceLevel.RECONCILIATION_OK,
    LoadEvidenceLevel.READY,
]


@dataclass
class EALoadEvidence:
    """Accumulated proof that EA is live and reconciled."""

    level: LoadEvidenceLevel = LoadEvidenceLevel.NONE
    file_present: bool = False
    compile_valid: bool = False
    terminal_detected: bool = False
    hello_received: bool = False
    heartbeat_received: bool = False
    reconciliation_ok: bool = False
    protocol_version: Optional[str] = None
    ea_version: Optional[str] = None
    terminal_id: Optional[str] = None
    session_id: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def recompute(self) -> LoadEvidenceLevel:
        flags = {
            LoadEvidenceLevel.FILE_PRESENT: self.file_present,
            LoadEvidenceLevel.COMPILE_VALID: self.compile_valid,
            LoadEvidenceLevel.TERMINAL_DETECTED: self.terminal_detected,
            LoadEvidenceLevel.EA_HELLO_RECEIVED: self.hello_received,
            LoadEvidenceLevel.HEARTBEAT_RECEIVED: self.heartbeat_received,
            LoadEvidenceLevel.RECONCILIATION_OK: self.reconciliation_ok,
            LoadEvidenceLevel.READY: (
                self.file_present
                and self.terminal_detected
                and self.hello_received
                and self.heartbeat_received
                and self.reconciliation_ok
            ),
        }
        level = LoadEvidenceLevel.NONE
        for step in _LADDER:
            if flags.get(step):
                level = step
            else:
                break
        if flags[LoadEvidenceLevel.READY]:
            level = LoadEvidenceLevel.READY
        self.level = level
        return level

    @property
    def allows_ready(self) -> bool:
        return self.level == LoadEvidenceLevel.READY

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "file_present": self.file_present,
            "compile_valid": self.compile_valid,
            "terminal_detected": self.terminal_detected,
            "hello_received": self.hello_received,
            "heartbeat_received": self.heartbeat_received,
            "reconciliation_ok": self.reconciliation_ok,
            "allows_ready": self.allows_ready,
            "protocol_version": self.protocol_version,
            "ea_version": self.ea_version,
            "terminal_id": self.terminal_id,
            "session_id": self.session_id,
            "notes": list(self.notes),
        }
