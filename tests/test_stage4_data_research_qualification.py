"""Stage 4.1 — data/research platform qualification tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage4_data_research_qualification import (
    qualify_content_hash,
    qualify_dataset_snapshot,
    qualify_data_quality,
    qualify_artifact_validation,
    qualify_experiment_reproducibility,
    qualify_research_cannot_authorize_execution,
    run_stage4,
)


def test_content_hash_deterministic():
    r = qualify_content_hash()
    assert r.status == "PASS"


def test_dataset_immutability_and_leakage():
    r = qualify_dataset_snapshot()
    assert r.status == "PASS"


def test_data_quality_fail_closed():
    r = qualify_data_quality()
    assert r.status == "PASS"


def test_artifact_validation_fail_closed(tmp_path: Path):
    r = qualify_artifact_validation(tmp_path)
    assert r.status == "PASS"


def test_experiment_reproducibility_20():
    r = qualify_experiment_reproducibility()
    assert r.status == "PASS"
    assert r.details["unique"] == 1


def test_research_cannot_authorize_execution():
    r = qualify_research_cannot_authorize_execution()
    assert r.status == "PASS"
    assert r.details["live_authorized"] is False


def test_run_stage4_all_material_pass():
    out = run_stage4()
    for area, status in out["statuses"].items():
        assert status == "PASS", (area, status)
