"""Stage 2.1 — integrated EventBus worker, recovery matrix, RiskEngine/ExecutionStore."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage2_integrated_replay import (
    IntegratedConfig,
    run_integrated,
    run_integrated_n,
)


def test_integrated_deterministic_pair():
    cfg = IntegratedConfig(seed=7)
    a = run_integrated(cfg, run_id="a")
    b = run_integrated(cfg, run_id="b")
    assert a.semantic_bundle() == b.semantic_bundle()


def test_integrated_100_runs():
    cfg = IntegratedConfig(seed=11)
    results = run_integrated_n(cfg, 100)
    assert len(results) == 100
    assert len({r.final_result_hash for r in results}) == 1


def test_recovery_boundary_matrix_all_pass():
    r = run_integrated(IntegratedConfig(seed=3))
    recovery = r.metadata["recovery"]
    for name, row in recovery.items():
        assert row["status"] == "PASS", name
        assert row["equal"] is True


def test_duplicate_effects_zero():
    r = run_integrated(IntegratedConfig(seed=5))
    assert r.metadata["duplicate_effects"] == 0


def test_divergence_input_mutation():
    cfg = IntegratedConfig(seed=9)
    base = run_integrated(cfg)
    mut = run_integrated(cfg, mutate="input")
    assert base.final_result_hash != mut.final_result_hash
    assert base.input_hash != mut.input_hash


def test_divergence_config_mutation():
    cfg = IntegratedConfig(seed=9)
    base = run_integrated(cfg)
    mut = run_integrated(cfg, mutate="config")
    assert base.final_result_hash != mut.final_result_hash


def test_risk_hash_stable_and_paper_only():
    r = run_integrated(IntegratedConfig(seed=2))
    assert r.risk_hash
    assert r.execution_store_hash
    assert r.metadata.get("live_authorized") is False


def test_handler_path_produces_state():
    r = run_integrated(IntegratedConfig(seed=4))
    assert r.handler_result_hash
    assert r.event_stream_hash
