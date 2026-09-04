"""Stage 2.3 — real production engines multi-handler qualification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage2_3_real_engines import S23Config, run_s23, run_s23_n, HANDLER_INVENTORY


def test_real_engines_deterministic_pair():
    cfg = S23Config(seed=7)
    a = run_s23(cfg, run_id="a")
    b = run_s23(cfg, run_id="b")
    assert a.final_result_hash == b.final_result_hash
    assert a.metadata["engine_mode"] == "REAL_PRODUCTION"


def test_real_engines_100_runs():
    results = run_s23_n(S23Config(seed=11), 100)
    assert len(results) == 100
    assert len({r.final_result_hash for r in results}) == 1


def test_inventory_real_handlers():
    real = [h for h in HANDLER_INVENTORY if h["status"] == "REAL"]
    assert len(real) >= 7


def test_order_dependent_divergence():
    cfg = S23Config(seed=5)
    a = run_s23(cfg, order="canonical")
    b = run_s23(cfg, order="reversed")
    assert a.final_result_hash != b.final_result_hash


def test_seed_divergence():
    cfg = S23Config(seed=9)
    base = run_s23(cfg)
    mut = run_s23(cfg, mutate="seed")
    assert base.final_result_hash != mut.final_result_hash


def test_no_live():
    r = run_s23(S23Config(seed=2))
    assert r.metadata["live_authorized"] is False
    assert r.metadata["duplicate_effects"] == 0
    assert r.metadata["startup"]["live"] is False
