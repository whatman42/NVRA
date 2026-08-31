"""Phase 4A — Research & Evidence Engine tests (no live trading claims)."""

from __future__ import annotations

from pathlib import Path

import pytest

from god.memory.database import Database
from god.memory.repositories import MemoryStore
from god.research import ResearchEngine
from god.research.anomaly import AnomalyDetector
from god.research.assessment import assess_evidence
from god.research.models import (
    EvidenceRecord,
    ExperimentOutcome,
    SourceReliability,
)
from god.research.provenance import content_hash
from god.research.sources import SourceTracker


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    db = Database(tmp_path / "research4a.db")
    return MemoryStore(db)


@pytest.fixture
def engine(store: MemoryStore) -> ResearchEngine:
    return ResearchEngine(store)


def test_content_hash_deterministic():
    assert content_hash({"a": 1, "b": 2}) == content_hash({"b": 2, "a": 1})
    assert content_hash("x") != content_hash("y")


def test_ingest_and_fact(engine: ResearchEngine):
    prov, report = engine.ingest_data({"bars": [1, 2, 3]}, origin="synthetic")
    assert prov.content_hash
    assert report.anomalous is False
    fact = engine.record_fact("observed 3 bars", provenance_id=prov.provenance_id)
    assert fact.fact_id in engine._facts


def test_claim_evidence_assessment(engine: ResearchEngine):
    claim = engine.propose_claim("candidate: mean-reversion may appear in regime X")
    ev = engine.attach_evidence(claim.claim_id, "synthetic support", weight=1.0)
    assert ev.claim_id == claim.claim_id
    result = engine.assess_claim(claim.claim_id)
    assert 0.0 <= result.score <= 1.0
    assert result.supporting == 1


def test_hypothesis_not_system_law(engine: ResearchEngine):
    h = engine.propose_hypothesis(
        "candidate parameter set for later experiment",
        metadata={"candidates": {"indicator_name": "RSI", "window": 14}},
    )
    assert h.status == "PROPOSED"
    assert "RSI" in str(h.metadata)
    assert h.status != "ACTIVE_STRATEGY"


def test_experiment_pass_and_fail_registry(engine: ResearchEngine):
    exp = engine.design_experiment("smoke_validation", config={"mode": "unit"})
    engine.run_experiment_record(
        exp.experiment_id, outcome=ExperimentOutcome.PASS, metrics={"ok": 1}
    )
    failed = engine.design_experiment("expected_fail")
    engine.run_experiment_record(
        failed.experiment_id, outcome=ExperimentOutcome.FAIL, notes="assert failed"
    )
    fails = engine.failed_experiments()
    assert any(f.experiment_id == failed.experiment_id for f in fails)


def test_source_quarantine_on_anomalies():
    t = SourceTracker()
    s = t.register("noisy-feed")
    for _ in range(3):
        t.record_anomaly(s.source_id)
    assert t.get(s.source_id).reliability == SourceReliability.QUARANTINED


def test_anomaly_empty_and_flood():
    d = AnomalyDetector()
    r = d.inspect("")
    assert r.anomalous and "empty_payload" in r.reasons
    for _ in range(5):
        r = d.inspect("same")
    assert "hash_flood" in r.reasons


def test_assess_evidence_quarantined_zero():
    from god.research.models import SourceProfile

    src = SourceProfile(
        source_id="q", name="q", reliability=SourceReliability.QUARANTINED
    )
    ev = [
        EvidenceRecord(
            evidence_id="e1", claim_id="c1", summary="x", weight=10.0, created_at=""
        )
    ]
    r = assess_evidence("c1", ev, source=src)
    assert r.score == 0.0


def test_audit_trail_immutable(engine: ResearchEngine, store: MemoryStore):
    engine.propose_claim("audit me")
    rows = store.list_audit(limit=20)
    assert any(a.component == "research" for a in rows)
    assert any(a.action == "claim_proposed" for a in rows)


def test_experience_recorded(engine: ResearchEngine, store: MemoryStore):
    e = engine.record_experience("learned that empty sources are weak", kind="research")
    listed = store.list_experiences(limit=10)
    assert any(x.experience_id == e.experience_id for x in listed)


def test_no_hardcoded_trading_thresholds_in_assessment_module():
    import god.research.assessment as mod

    src = Path(mod.__file__).read_text()
    for forbidden in ("Sharpe", "RRR", "risk_percent", "MACD", "Bollinger"):
        assert forbidden not in src


def test_pipeline_restart_safe(tmp_path: Path):
    db_path = tmp_path / "r.db"
    db = Database(db_path)
    store = MemoryStore(db)
    eng = ResearchEngine(store)
    c1 = eng.propose_claim("stable claim text")
    db.close()

    db2 = Database(db_path)
    store2 = MemoryStore(db2)
    audits = store2.list_audit(limit=50)
    assert any(a.action == "claim_proposed" for a in audits)
    assert c1.content_hash == content_hash("stable claim text")
