"""Stage 8 — compute/artifact/model infrastructure qualification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage8_compute_artifact_qualification import (
    qualify_experiment_spec,
    qualify_artifact_identity,
    qualify_promotion_gate,
    qualify_determinism,
    qualify_inv003_ml_boundary,
    run_stage8,
)


def test_experiment_spec():
    assert qualify_experiment_spec().status == "PASS"


def test_artifact_identity(tmp_path: Path):
    r = qualify_artifact_identity(tmp_path)
    assert r.status == "PASS"
    assert r.details["integrity_bypass"] == 0


def test_promotion_gate(tmp_path: Path):
    assert qualify_promotion_gate(tmp_path).status == "PASS"


def test_determinism_20():
    r = qualify_determinism(20)
    assert r.status == "PASS"
    assert r.details["unique"] == 1


def test_inv003():
    assert qualify_inv003_ml_boundary().status == "PASS"


def test_run_stage8_all_pass():
    out = run_stage8()
    for k, v in out["statuses"].items():
        assert v == "PASS", (k, v)
    assert out["integrity_bypass"] == 0
    assert "Stage 10" in out["real_capital"]
