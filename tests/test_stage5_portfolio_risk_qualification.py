"""Stage 5.1 — portfolio & risk qualification tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from research.harness.stage5_portfolio_risk_qualification import (
    qualify_portfolio_state,
    qualify_exposure,
    qualify_risk_engine_authority,
    qualify_drawdown,
    qualify_determinism,
    qualify_ml_boundary,
    run_stage5,
)


def test_portfolio_state():
    assert qualify_portfolio_state().status == "PASS"


def test_exposure_deterministic():
    assert qualify_exposure().status == "PASS"


def test_risk_engine_authority():
    assert qualify_risk_engine_authority().status == "PASS"


def test_drawdown_blocks():
    assert qualify_drawdown().status == "PASS"


def test_determinism_20():
    r = qualify_determinism(20)
    assert r.status == "PASS"
    assert r.details["unique"] == 1


def test_ml_cannot_raise_ceiling():
    assert qualify_ml_boundary().status == "PASS"


def test_run_stage5_all_pass():
    out = run_stage5()
    for k, v in out["statuses"].items():
        assert v == "PASS", (k, v)
