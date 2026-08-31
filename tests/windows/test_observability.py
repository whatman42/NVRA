"""Health snapshot + load evidence ladder."""

from __future__ import annotations

from god.bridge.lifecycle import DeploymentState, DeploymentStatus
from god.bridge.windows.evidence import EALoadEvidence, LoadEvidenceLevel
from god.bridge.windows.observability import (
    ComponentStatus,
    ExecutionGate,
    build_health_snapshot,
)


def test_evidence_file_only_not_ready():
    e = EALoadEvidence(file_present=True)
    e.recompute()
    assert e.level == LoadEvidenceLevel.FILE_PRESENT
    assert not e.allows_ready


def test_evidence_full_ladder_ready():
    e = EALoadEvidence(
        file_present=True,
        compile_valid=True,
        terminal_detected=True,
        hello_received=True,
        heartbeat_received=True,
        reconciliation_ok=True,
    )
    e.recompute()
    assert e.level == LoadEvidenceLevel.READY
    assert e.allows_ready


def test_snapshot_locks_without_evidence():
    dep = DeploymentStatus(state=DeploymentState.READY)
    dep.set_state(DeploymentState.READY)
    snap = build_health_snapshot(
        deployment=dep,
        evidence=EALoadEvidence(file_present=True),
        is_windows=False,
    )
    assert snap.execution_status == ExecutionGate.LOCKED
    assert any("pending" in n.lower() for n in snap.notes)


def test_snapshot_ready_when_evidence_and_deployment():
    dep = DeploymentStatus()
    dep.set_state(DeploymentState.READY)
    e = EALoadEvidence(
        file_present=True,
        terminal_detected=True,
        hello_received=True,
        heartbeat_received=True,
        reconciliation_ok=True,
    )
    snap = build_health_snapshot(deployment=dep, evidence=e, is_windows=True)
    assert snap.execution_status == ExecutionGate.READY
    assert snap.brain_status == ComponentStatus.ONLINE


def test_no_strategy_fields_in_snapshot():
    snap = build_health_snapshot(is_windows=False)
    d = snap.to_dict()
    blob = str(d).lower()
    assert "rsi" not in blob
    assert "macd" not in blob
