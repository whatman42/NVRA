"""Smoke tests for research Phase 0 results presence — no production mutation."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "research" / "results"


def test_phase0_result_files_exist():
    required = [
        "baseline_env.json",
        "exp_dr_01.json",
        "exp_dr_02.json",
        "exp_dr_03.json",
        "exp_dr_04.json",
        "exp_dr_05.json",
        "exp_dr_06.json",
        "exp_dr_07.json",
        "exp_dr_08.json",
        "exp_dr_14.json",
        "exp_dr_18.json",
        "benchmarks_phase0.json",
    ]
    missing = [n for n in required if not (RESULTS / n).exists()]
    assert not missing, f"missing {missing}"


def test_exp_dr_01_pass():
    import json
    d = json.loads((RESULTS / "exp_dr_01.json").read_text())
    assert d["status"] == "PASS"
    assert d["equal_abc"] is True


def test_exp_dr_14_reject_rate():
    import json
    d = json.loads((RESULTS / "exp_dr_14.json").read_text())
    assert d["status"] == "PASS"
    assert d["mutation_reject_rate"] == 1.0
