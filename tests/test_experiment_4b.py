"""Phase 4B — Experiment engine + validation metadata tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from god.memory.database import Database
from god.memory.repositories import MemoryStore
from god.research import ResearchEngine
from god.research.experiments import ExperimentEngine, ExperimentOutcomeExt
from god.research.validation import record_validation


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(Database(tmp_path / "e4b.db"))


@pytest.fixture
def eng(store: MemoryStore) -> ExperimentEngine:
    return ExperimentEngine(ResearchEngine(store))


@pytest.mark.parametrize(
    "outcome",
    [
        ExperimentOutcomeExt.PASS,
        ExperimentOutcomeExt.FAIL,
        ExperimentOutcomeExt.REJECTED,
        ExperimentOutcomeExt.INCONCLUSIVE,
        ExperimentOutcomeExt.TIMEOUT,
        ExperimentOutcomeExt.INVALID,
        ExperimentOutcomeExt.OVERFIT_FLAG,
    ],
)
def test_all_outcomes(eng: ExperimentEngine, outcome: ExperimentOutcomeExt):
    meta = eng.design("exp", random_seed=42, methodology="unit")
    done = eng.complete(meta.experiment_id, outcome, failure_reason=outcome.value)
    assert done.outcome == outcome.value
    assert done.random_seed == 42


def test_failed_experiments_retained(eng: ExperimentEngine):
    for i in range(5):
        m = eng.design(f"f{i}", family_id="fam-1")
        eng.complete(m.experiment_id, ExperimentOutcomeExt.FAIL, failure_reason="x")
    p = eng.design("pass1", family_id="fam-1")
    eng.complete(p.experiment_id, ExperimentOutcomeExt.PASS)
    failed = eng.list_failed_metadata()
    assert len(failed) >= 5


def test_multiple_testing_metadata(eng: ExperimentEngine):
    fid = "family-mt"
    for i in range(3):
        m = eng.design(f"mt{i}", family_id=fid, parameters={"i": i})
        assert m.family_id == fid
        assert m.selection_bias_note
    members = eng.family_members(fid)
    assert len(members) == 3
    assert all(m.family_size == 3 for m in members)


def test_validation_metadata_oos_wf_seed():
    v = record_validation(
        "exp-1",
        oos=True,
        walk_forward=True,
        robustness=True,
        random_seed=7,
        methodology="holdout",
        dataset_identity="ds-A",
        lineage=["h1", "exp-1"],
    )
    d = v.to_dict()
    assert d["oos_recorded"] is True
    assert d["walk_forward_recorded"] is True
    assert d["random_seed"] == 7
    flags = v.as_flags()
    assert flags["robustness_recorded"] is True


def test_validation_flags_on_complete(eng: ExperimentEngine):
    m = eng.design("val", random_seed=1, methodology="wf")
    v = record_validation(m.experiment_id, oos=True, walk_forward=True, random_seed=1)
    done = eng.complete(
        m.experiment_id,
        ExperimentOutcomeExt.INCONCLUSIVE,
        validation_flags=v.as_flags(),
    )
    assert done.validation_flags.get("oos_recorded") is True


def test_restart_audit_persistence(tmp_path: Path):
    path = tmp_path / "r.db"
    db = Database(path)
    store = MemoryStore(db)
    research = ResearchEngine(store)
    eng = ExperimentEngine(research)
    m = eng.design("persist", random_seed=99)
    eng.complete(m.experiment_id, ExperimentOutcomeExt.FAIL, failure_reason="boom")
    db.close()

    db2 = Database(path)
    store2 = MemoryStore(db2)
    audits = store2.list_audit(limit=100)
    assert any(a.action == "experiment_failed" for a in audits)


def test_no_sharpe_law_in_4b_modules():
    root = Path(__file__).resolve().parents[1] / "god" / "research"
    blob = ""
    for sub in ("curiosity", "experiments", "validation"):
        for p in (root / sub).glob("*.py"):
            blob += p.read_text()
    for tok in ("Sharpe >", "p-value <", "RRR >", "confidence > 0.6"):
        assert tok not in blob
