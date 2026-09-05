"""Stage 10 — pre-LIVE real-capital gate tests (NO real orders)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage10_real_capital_prelive_qualification import (
    qualify_no_automatic_live,
    qualify_production_gate_blocks,
    qualify_risk_blocks_live_path,
    qualify_real_capital_prerequisites,
    run_stage10,
)


def test_no_automatic_live():
    assert qualify_no_automatic_live().status == "PASS"


def test_production_gate_blocks():
    assert qualify_production_gate_blocks().status == "PASS"


def test_risk_blocks():
    assert qualify_risk_blocks_live_path().status == "PASS"


def test_real_capital_prerequisites_blocked():
    r = qualify_real_capital_prerequisites()
    assert r.status == "BLOCKED"


def test_run_stage10_verdict_blocked():
    out = run_stage10()
    assert out["verdict"] == "BLOCKED"
    for c, n in out["safety_counters"].items():
        assert n == 0, (c, n)
    assert out["statuses"]["no_automatic_live"] == "PASS"
    assert out["statuses"]["real_capital_prerequisites"] == "BLOCKED"
