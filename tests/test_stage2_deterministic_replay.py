"""Stage 2 scientific verification — deterministic replay qualification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage2_deterministic_replay import ReplayConfig, run_n, run_replay


def test_r01_same_input_same_seed():
    cfg = ReplayConfig(seed=7)
    a = run_replay(cfg, run_id="r1a")
    b = run_replay(cfg, run_id="r1b")
    assert a.semantic_bundle() == b.semantic_bundle()


def test_r02_100_repeated_runs_single_hash():
    cfg = ReplayConfig(seed=11)
    results = run_n(cfg, 100)
    hashes = {r.final_result_hash for r in results}
    assert len(hashes) == 1
    assert len(results) == 100


def test_r03_event_stream_stable():
    cfg = ReplayConfig(seed=3)
    a = run_replay(cfg, run_id="a")
    b = run_replay(cfg, run_id="b")
    assert a.event_stream_hash == b.event_stream_hash


def test_r01b_seed_divergence_detected():
    a = run_replay(ReplayConfig(seed=1), run_id="a")
    b = run_replay(ReplayConfig(seed=2), run_id="b")
    assert a.final_result_hash != b.final_result_hash
    assert a.input_hash != b.input_hash


def test_event_order_reverse_changes_stream_hash_keeps_analysis():
    cfg = ReplayConfig(seed=5)
    canon = run_replay(cfg, run_id="c")
    rev = run_replay(cfg, run_id="r", event_order="reversed")
    assert canon.analysis_hash == rev.analysis_hash
    assert canon.event_stream_hash != rev.event_stream_hash


def test_no_live_in_replay_surfaces():
    r = run_replay(ReplayConfig(seed=9), run_id="x")
    assert r.risk_hash
    assert r.decision_hash
    assert r.execution_intent_hash


def test_reproducibility_metadata_present():
    r = run_replay(ReplayConfig(seed=4), run_id="meta")
    assert r.experiment_id
    assert r.run_id
    assert r.python_version
    assert r.platform
    assert r.seed == 4
    assert r.input_hash
    assert r.config_hash
    assert r.final_result_hash


def test_orchestration_models_and_eventbus():
    from god.orchestration import EventBus
    from god.orchestration.models import EventType, create_context, create_event

    ctx = create_context(correlation_id="t")
    e = create_event(EventType.OBSERVATION, correlation_id="t", context_id=ctx.context_id)
    bus = EventBus()
    assert bus.publish(e) is True
    assert bus.consume().event_id == e.event_id
