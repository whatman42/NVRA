"""Stage 9 — governance / security / observability qualification."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage9_governance_security_qualification import (
    qualify_production_gate,
    qualify_safe_mode,
    qualify_secret_scanning,
    qualify_determinism,
    qualify_invariants,
    run_stage9,
)


def test_production_gate_default_no_go():
    assert qualify_production_gate().status == "PASS"


def test_safe_mode_blocks():
    assert qualify_safe_mode().status == "PASS"


def test_secret_scanning():
    assert qualify_secret_scanning().status == "PASS"


def test_determinism_20():
    r = qualify_determinism(20)
    assert r.status == "PASS"
    assert r.details["unique"] == 1


def test_invariants():
    assert qualify_invariants().status == "PASS"


def test_run_stage9_all_pass():
    out = run_stage9()
    for k, v in out["statuses"].items():
        assert v == "PASS", (k, v)
    for c, n in out["safety_counters"].items():
        assert n == 0, (c, n)
    assert "Stage 10" in out["real_capital"]
