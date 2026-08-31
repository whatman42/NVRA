"""Typed health snapshot for Control Center GUI (not a trading terminal)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.bridge.lifecycle import DeploymentState, DeploymentStatus
from god.bridge.windows.evidence import EALoadEvidence, LoadEvidenceLevel


class ComponentStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    LOCKED = "LOCKED"
    READY = "READY"
    UNAVAILABLE = "UNAVAILABLE"
    PENDING = "PENDING"


class ExecutionGate(str, Enum):
    LOCKED = "LOCKED"
    READY = "READY"


@dataclass
class NUNGHealthSnapshot:
    """Machine-readable system health for GUI / diagnostics."""

    brain_status: ComponentStatus = ComponentStatus.UNKNOWN
    bridge_status: ComponentStatus = ComponentStatus.UNKNOWN
    ea_status: ComponentStatus = ComponentStatus.UNKNOWN
    terminal_status: ComponentStatus = ComponentStatus.UNKNOWN
    ipc_status: ComponentStatus = ComponentStatus.UNKNOWN
    heartbeat_status: ComponentStatus = ComponentStatus.UNKNOWN
    reconciliation_status: ComponentStatus = ComponentStatus.UNKNOWN
    execution_status: ExecutionGate = ExecutionGate.LOCKED
    memory_status: ComponentStatus = ComponentStatus.UNKNOWN
    research_status: ComponentStatus = ComponentStatus.UNAVAILABLE
    hardware_status: ComponentStatus = ComponentStatus.UNKNOWN
    deployment_state: Optional[str] = None
    load_evidence_level: Optional[str] = None
    uptime_s: Optional[float] = None
    last_heartbeat: Optional[str] = None
    last_observation: Optional[str] = None
    last_decision: Optional[str] = None
    last_error: Optional[str] = None
    tick_to_brain_ms: Optional[float] = None
    brain_to_ea_ms: Optional[float] = None
    round_trip_ms: Optional[float] = None
    notes: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "brain_status": self.brain_status.value,
            "bridge_status": self.bridge_status.value,
            "ea_status": self.ea_status.value,
            "terminal_status": self.terminal_status.value,
            "ipc_status": self.ipc_status.value,
            "heartbeat_status": self.heartbeat_status.value,
            "reconciliation_status": self.reconciliation_status.value,
            "execution_status": self.execution_status.value,
            "memory_status": self.memory_status.value,
            "research_status": self.research_status.value,
            "hardware_status": self.hardware_status.value,
            "deployment_state": self.deployment_state,
            "load_evidence_level": self.load_evidence_level,
            "uptime_s": self.uptime_s,
            "last_heartbeat": self.last_heartbeat,
            "last_observation": self.last_observation,
            "last_decision": self.last_decision,
            "last_error": self.last_error,
            "tick_to_brain_ms": self.tick_to_brain_ms,
            "brain_to_ea_ms": self.brain_to_ea_ms,
            "round_trip_ms": self.round_trip_ms,
            "notes": list(self.notes),
            "metadata": dict(self.metadata),
        }


def build_health_snapshot(
    *,
    deployment: Optional[DeploymentStatus] = None,
    evidence: Optional[EALoadEvidence] = None,
    is_windows: bool = False,
    brain_online: bool = True,
    memory_ok: bool = True,
    last_error: Optional[str] = None,
    latency: Optional[dict] = None,
) -> NUNGHealthSnapshot:
    """Compose snapshot from frozen lifecycle + load evidence."""
    snap = NUNGHealthSnapshot(
        brain_status=ComponentStatus.ONLINE if brain_online else ComponentStatus.OFFLINE,
        memory_status=ComponentStatus.ONLINE if memory_ok else ComponentStatus.DEGRADED,
        research_status=ComponentStatus.UNAVAILABLE,
        hardware_status=ComponentStatus.ONLINE if is_windows else ComponentStatus.PENDING,
        last_error=last_error,
    )
    notes: list[str] = []
    if not is_windows:
        notes.append("Architecture verified; real Windows/MT5 verification pending.")

    if deployment is not None:
        snap.deployment_state = deployment.state.value
        if deployment.allows_execution():
            snap.execution_status = ExecutionGate.READY
        else:
            snap.execution_status = ExecutionGate.LOCKED
        if deployment.state == DeploymentState.READY:
            snap.bridge_status = ComponentStatus.READY
        elif deployment.state in (DeploymentState.FAILED, DeploymentState.DEGRADED):
            snap.bridge_status = ComponentStatus.DEGRADED
        elif deployment.state == DeploymentState.RECOVERY:
            snap.bridge_status = ComponentStatus.LOCKED
        else:
            snap.bridge_status = ComponentStatus.PENDING
        if deployment.last_error:
            snap.last_error = deployment.last_error

    if evidence is not None:
        evidence.recompute()
        snap.load_evidence_level = evidence.level.value
        snap.ea_status = (
            ComponentStatus.READY
            if evidence.level == LoadEvidenceLevel.READY
            else ComponentStatus.PENDING
            if evidence.file_present
            else ComponentStatus.OFFLINE
        )
        snap.terminal_status = (
            ComponentStatus.ONLINE if evidence.terminal_detected else ComponentStatus.OFFLINE
        )
        snap.ipc_status = (
            ComponentStatus.ONLINE if evidence.hello_received else ComponentStatus.OFFLINE
        )
        snap.heartbeat_status = (
            ComponentStatus.ONLINE if evidence.heartbeat_received else ComponentStatus.OFFLINE
        )
        snap.reconciliation_status = (
            ComponentStatus.READY if evidence.reconciliation_ok else ComponentStatus.PENDING
        )
        if evidence.allows_ready and snap.execution_status == ExecutionGate.READY:
            snap.execution_status = ExecutionGate.READY
        else:
            snap.execution_status = ExecutionGate.LOCKED

    if latency:
        snap.tick_to_brain_ms = latency.get("tick_to_brain_ms")
        snap.brain_to_ea_ms = latency.get("brain_to_ea_ms")
        snap.round_trip_ms = latency.get("round_trip_ms")

    snap.notes = notes
    return snap
