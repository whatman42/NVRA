"""Production checkpoint semantic gate tests (P0-A)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

import pytest

from god.institutional.checkpoint import CheckpointStore
from god.institutional.checkpoint_schema import (
    CheckpointValidationError,
    is_lifecycle_claim,
    validate_lifecycle_state,
)


def _valid_lifecycle(**over):
    base = {
        "schema_version": "1.0",
        "sequence": 3,
        "lifecycle": "RUNNING",
        "recon_complete": True,
        "updated_ns": time.time_ns(),
    }
    base.update(over)
    return base


def test_opaque_workflow_still_saves_and_loads(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    s.save("r1", "observation", {"symbol": "X", "context": {"a": 1}})
    got = s.load("r1")
    assert got is not None
    assert got["node"] == "observation"
    assert got["state"]["symbol"] == "X"
    assert "validation" not in got


def test_valid_lifecycle_save_load(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    st = _valid_lifecycle()
    s.save("r1", "RUNNING", st)
    got = s.load("r1")
    assert got is not None
    assert got["validation"]["trusted_ready"] is True
    assert got["validation"]["trusted_execution"] is False
    assert s.load_trusted_ready("r1") is not None


def test_reject_empty_lifecycle_claim(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    with pytest.raises(CheckpointValidationError):
        s.save("r1", "READY", {})


def test_reject_ready_without_recon(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    st = _valid_lifecycle(lifecycle="READY", recon_complete=False)
    with pytest.raises(CheckpointValidationError):
        s.save("r1", "READY", st)


def test_load_ready_without_recon_fail_closed(tmp_path: Path):
    db = tmp_path / "c.db"
    s = CheckpointStore(db)
    payload = json.dumps(
        {
            "schema_version": "1.0",
            "sequence": 1,
            "lifecycle": "READY",
            "recon_complete": False,
            "updated_ns": time.time_ns(),
        }
    )
    with sqlite3.connect(db) as c:
        c.execute(
            "INSERT INTO checkpoints VALUES(?,?,?,?)",
            ("r1", "READY", payload, time.time_ns()),
        )
        c.commit()
    assert s.load("r1") is None
    assert s.load_trusted_ready("r1") is None


def test_malformed_json_fail_closed(tmp_path: Path):
    db = tmp_path / "c.db"
    s = CheckpointStore(db)
    s.save("r1", "observation", {"ok": True})
    with sqlite3.connect(db) as c:
        c.execute("UPDATE checkpoints SET state_json=? WHERE run_id='r1'", ("NOTJSON",))
        c.commit()
    assert s.load("r1") is None


def test_unsupported_schema_rejected(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    st = _valid_lifecycle(schema_version="99.0")
    with pytest.raises(CheckpointValidationError):
        s.save("r1", "RUNNING", st)


def test_invalid_enum_rejected(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    st = _valid_lifecycle(lifecycle="NOT_REAL")
    with pytest.raises(CheckpointValidationError):
        s.save("r1", "NOT_REAL", st)


def test_wrong_type_rejected():
    r = validate_lifecycle_state(
        {**_valid_lifecycle(), "sequence": "x"}, node="RUNNING"
    )
    assert r.ok is False
    assert r.classification == "REJECT"


def test_unknown_and_safe_mode_not_trusted_ready(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    for lc in ("UNKNOWN", "SAFE_MODE"):
        st = _valid_lifecycle(lifecycle=lc, recon_complete=False)
        s.save("r1", lc, st)
        got = s.load("r1")
        assert got is not None
        assert got["validation"]["trusted_ready"] is False
        assert got["validation"]["trusted_execution"] is False
        assert s.load_trusted_ready("r1") is None


def test_stale_state_not_trusted(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    st = _valid_lifecycle(updated_ns=1)
    with pytest.raises(CheckpointValidationError):
        s.save("r1", "RUNNING", st)


def test_sequence_regression_rejected():
    r = validate_lifecycle_state(
        _valid_lifecycle(sequence=2), node="RUNNING", last_sequence=5
    )
    assert r.ok is False
    assert "sequence_regression" in r.reasons


def test_exec_inconsistent_rejected(tmp_path: Path):
    s = CheckpointStore(tmp_path / "c.db")
    st = _valid_lifecycle(order_pending=True, flat=True)
    with pytest.raises(CheckpointValidationError):
        s.save("r1", "RUNNING", st)


def test_is_lifecycle_claim_opaque():
    assert is_lifecycle_claim("observation", {"symbol": "X"}) is False
    assert is_lifecycle_claim("RUNNING", {"schema_version": "1.0"}) is True


def test_kernel_opaque_checkpoints_still_work(tmp_path: Path):
    from god.institutional.kernel import InstitutionalKernel, KernelConfig
    from god.institutional.agent_graph import DecisionPacket

    cfg = KernelConfig(state_dir=str(tmp_path))
    k = InstitutionalKernel(cfg)
    k.publish_observation("EURUSD", {"px": 1.1})
    k.submit_decision(DecisionPacket(symbol="EURUSD", action="HOLD", confidence=0.5, thesis="t"))
    k.drain()
    assert k.last_result is not None
