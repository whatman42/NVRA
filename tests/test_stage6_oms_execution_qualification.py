"""Stage 6.1 — OMS/EMS execution qualification tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage6_oms_execution_qualification import (
    qualify_order_state_machine,
    qualify_paper_submit_and_idempotency,
    qualify_risk_gate,
    qualify_determinism,
    run_stage6,
)


def test_order_state_machine():
    assert qualify_order_state_machine().status == "PASS"


def test_idempotency_zero_duplicates(tmp_path: Path):
    r = qualify_paper_submit_and_idempotency(tmp_path)
    assert r.status == "PASS"
    assert r.details["duplicate_effects"] == 0


def test_risk_gate(tmp_path: Path):
    assert qualify_risk_gate(tmp_path).status == "PASS"


def test_determinism_20():
    r = qualify_determinism(20)
    assert r.status == "PASS"
    assert r.details["unique"] == 1


def test_run_stage6_all_pass():
    out = run_stage6()
    for k, v in out["statuses"].items():
        assert v == "PASS", (k, v)
    assert out["duplicate_effects"] == 0
