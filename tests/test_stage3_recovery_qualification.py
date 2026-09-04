"""Stage 3.1 — checkpoint corruption, recovery chain, determinism."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage3_recovery_qualification import (
    scenario_corruption_matrix,
    recovery_to_execution_safety,
    deterministic_recovery_n,
    run_stage3,
)


def test_corruption_matrix_no_unsafe_ready(tmp_path: Path):
    results = scenario_corruption_matrix(tmp_path / "c.db")
    assert results
    for r in results:
        if r.name not in ("normal_save_reload", "atomic_replacement"):
            assert r.trusted_ready is False, r.name
            assert r.trusted_execution is False


def test_recovery_chain_counters_zero(tmp_path: Path):
    out = recovery_to_execution_safety(tmp_path / "chain.db")
    c = out["counters"]
    assert c["unauthorized_execution"] == 0
    assert c["stale_to_execution"] == 0
    assert c["corrupt_checkpoint_to_execution"] == 0
    assert c["unknown_to_execution"] == 0
    assert c["safe_mode_escape"] == 0
    assert out["checkpoint_trusted_execution_always_false"] is True
    assert out["live_authorized"] is False


def test_deterministic_recovery_20():
    d = deterministic_recovery_n(20)
    assert d["n"] == 20
    assert d["deterministic"] is True
    assert d["unique_hashes"] == 1


def test_run_stage3_aggregate():
    out = run_stage3()
    assert out["unsafe_ready"] == 0
    assert out["unsafe_execution"] == 0
    assert out["determinism"]["deterministic"] is True
    assert out["linux_systemd"] == "SERVICE_E2E_UNOBSERVABLE"
