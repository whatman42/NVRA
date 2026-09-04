"""Stage 7 — multi-venue / realistic PAPER execution qualification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage7_multi_venue_execution_qualification import (
    qualify_venue_abstraction,
    qualify_multi_venue_paper,
    qualify_determinism,
    qualify_risk_still_required,
    qualify_idempotency_cross_venue,
    run_stage7,
)


def test_venue_abstraction():
    assert qualify_venue_abstraction().status == "PASS"


def test_multi_venue_paper(tmp_path: Path):
    r = qualify_multi_venue_paper(tmp_path)
    assert r.status == "PASS"
    assert r.details["distinct_client_order_ids"] is True


def test_determinism_20():
    r = qualify_determinism(20)
    assert r.status == "PASS"
    assert r.details["unique"] == 1


def test_risk_still_required(tmp_path: Path):
    assert qualify_risk_still_required(tmp_path).status == "PASS"


def test_idempotency_cross_venue(tmp_path: Path):
    r = qualify_idempotency_cross_venue(tmp_path)
    assert r.status == "PASS"
    assert r.details["same_venue_duplicate_effects"] == 0


def test_run_stage7_all_pass():
    out = run_stage7()
    for k, v in out["statuses"].items():
        assert v == "PASS", (k, v)
    assert out["duplicate_effects"] == 0
    assert out["real_capital"] == "BLOCKED — Stage 10 only"
