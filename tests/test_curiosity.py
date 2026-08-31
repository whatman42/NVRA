"""Phase 4B — Curiosity engine tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from god.memory.database import Database
from god.memory.repositories import MemoryStore
from god.research import ResearchEngine
from god.research.curiosity import (
    AnomalyDetector,
    AnomalyType,
    CuriosityEngine,
    CuriosityEvent,
    ResearchTrigger,
    Severity,
)


@pytest.fixture
def store(tmp_path: Path) -> MemoryStore:
    return MemoryStore(Database(tmp_path / "c.db"))


@pytest.fixture
def research(store: MemoryStore) -> ResearchEngine:
    return ResearchEngine(store)


def test_curiosity_event_fields():
    ev = CuriosityEvent(
        event_id="e1",
        timestamp="t",
        source="s",
        anomaly_type=AnomalyType.VOLATILITY,
        severity=Severity.HIGH,
        evidence_refs=("a",),
        observation_refs=("o1",),
        research_trigger=True,
        provenance={"h": "x"},
    )
    d = ev.to_dict()
    assert d["event_id"] == "e1"
    assert d["anomaly_type"] == "VOLATILITY"
    assert d["research_trigger"] is True


def test_curiosity_no_execution_intent_fields():
    ev = CuriosityEvent(
        event_id="e2",
        timestamp="t",
        source="feed",
        anomaly_type=AnomalyType.VOLUME,
        severity=Severity.LOW,
    )
    assert ev.has_trade_payload() is False
    for bad in ("side", "lot", "order_type", "execution_intent"):
        assert bad not in ev.to_dict()


def test_anomaly_volatility_detection():
    det = AnomalyDetector()
    found = det.detect(
        {"volatility": 10.0, "volatility_baseline": 2.0, "observation_id": "o1"}
    )
    assert any(a.anomaly_type == AnomalyType.VOLATILITY for a in found)


def test_anomaly_empty_and_malformed():
    det = AnomalyDetector()
    empty = det.detect({})
    assert any(a.anomaly_type == AnomalyType.DATA for a in empty)
    bad = det.detect({"volatility": "x", "volatility_baseline": 1})
    assert any(a.detail.get("reason") == "malformed_volatility" for a in bad)


def test_curiosity_engine_emits_events():
    eng = CuriosityEngine()
    events = eng.process(
        {"volatility": 9, "volatility_baseline": 1, "observation_id": "obs-1"},
        source="unit",
    )
    assert len(events) >= 1
    assert all(isinstance(e, CuriosityEvent) for e in events)
    assert all(e.research_trigger for e in events)


def test_curiosity_idempotent_event_id():
    eng = CuriosityEngine()
    obs = {"volatility": 9, "volatility_baseline": 1, "observation_id": "obs-2"}
    a = eng.process(obs, event_id="fixed-id")
    b = eng.process(obs, event_id="fixed-id")
    assert len(a) >= 1
    assert b == []


def test_research_trigger_provenance(research: ResearchEngine, store: MemoryStore):
    ceng = CuriosityEngine()
    events = ceng.process(
        {"volume": 100, "volume_baseline": 10, "observation_id": "obs-3"},
        source="unit",
    )
    assert events
    trigger = ResearchTrigger(research)
    result = trigger.trigger(events[0])
    assert result.claim_id
    assert result.hypothesis_id
    assert result.experiment_id
    audits = store.list_audit(limit=50)
    assert any(a.action == "claim_proposed" for a in audits)


def test_no_order_tokens_in_curiosity_package():
    root = Path(__file__).resolve().parents[1] / "god" / "research" / "curiosity"
    blob = ""
    for p in root.glob("*.py"):
        blob += p.read_text()
    for tok in ("OrderSend", "OP_BUY", "OP_SELL"):
        assert tok not in blob
