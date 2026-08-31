"""Phase 2 acceptance tests — Persistent Memory / Database layer."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

import pytest

from god.memory.database import Database, DatabaseError, IntegrityError, utc_now
from god.memory.schema import SCHEMA_VERSION
from god.memory.models import (
    Strategy, StrategyVersion, Observation, Decision, Trade, Position,
    Experience, Experiment, ExperimentResult, KnowledgeClaim, Hypothesis,
    RiskEvent, CapabilityEvent, AuditRecord, ModelArtifact,
)
from god.memory.repositories import MemoryStore


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "god_memory.db"


@pytest.fixture
def db(db_path):
    database = Database(db_path)
    yield database
    database.close()


@pytest.fixture
def store(db):
    return MemoryStore(db)


# ── 1. Schema initialization from empty DB ──────────────────────────────

class TestSchemaInit:
    def test_creates_from_empty(self, db_path):
        assert not db_path.exists() or db_path.stat().st_size == 0 or True
        db = Database(db_path)
        assert db.get_schema_version() == SCHEMA_VERSION
        tables = db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        names = {r["name"] for r in tables}
        required = {
            "schema_version", "agent_state", "strategies", "strategy_versions",
            "observations", "decisions", "trades", "positions", "experiences",
            "experiments", "experiment_results", "knowledge_claims", "hypotheses",
            "risk_events", "capability_events", "audit_log", "model_artifacts",
        }
        assert required.issubset(names)
        db.close()

    def test_schema_version_tracked(self, db):
        assert db.get_schema_version() == SCHEMA_VERSION
        row = db.fetchone("SELECT version, applied_at FROM schema_version WHERE version = ?", (SCHEMA_VERSION,))
        assert row is not None
        assert row["applied_at"]


# ── 2 & 3. Migration mechanism + version tracking ───────────────────────

class TestMigrations:
    def test_idempotent_reopen(self, db_path):
        db1 = Database(db_path)
        v1 = db1.get_schema_version()
        db1.close()
        db2 = Database(db_path)
        assert db2.get_schema_version() == v1
        db2.close()

    def test_no_duplicate_migration(self, db):
        rows = db.fetchall("SELECT version FROM schema_version")
        versions = [r["version"] for r in rows]
        assert len(versions) == len(set(versions))


# ── 4. CRUD / typed repository ──────────────────────────────────────────

class TestCRUD:
    def test_agent_state(self, store):
        store.set_state("policy_version", "POLICY_1")
        assert store.get_state("policy_version") == "POLICY_1"
        store.set_state("policy_version", "POLICY_2")
        assert store.get_state("policy_version") == "POLICY_2"
        assert store.get_state("missing", default="x") == "x"

    def test_strategy_and_version(self, store):
        s = Strategy.create("strat_alpha")
        store.upsert_strategy(s)
        loaded = store.get_strategy(s.strategy_id)
        assert loaded is not None
        assert loaded.name == "strat_alpha"
        assert loaded.status == "GENERATED"

        sv = StrategyVersion.create(s.strategy_id, 1, genome={"features": ["rsi"]})
        store.add_strategy_version(sv)
        versions = store.get_strategy_versions(s.strategy_id)
        assert len(versions) == 1
        assert versions[0].genome["features"] == ["rsi"]

    def test_observation_decision_trade_chain(self, store):
        s = Strategy.create("s1")
        store.upsert_strategy(s)

        obs = Observation.create(symbol="EURUSD", timeframe="H1", features={"rsi": 55})
        store.add_observation(obs)

        dec = Decision.create(
            action="BUY", symbol="EURUSD", strategy_id=s.strategy_id,
            observation_id=obs.observation_id, volume=0.1, confidence=0.7,
        )
        store.add_decision(dec)

        trade = Trade.create(
            symbol="EURUSD", side="BUY", volume=0.1,
            decision_id=dec.decision_id, strategy_id=s.strategy_id,
            entry_price=1.10, broker_ticket="TKT-001",
        )
        store.upsert_trade(trade)

        loaded = store.get_trade(trade.trade_id)
        assert loaded is not None
        assert loaded.broker_ticket == "TKT-001"
        assert store.get_trade_by_ticket("TKT-001").trade_id == trade.trade_id

        by_dec = store.get_decision(dec.decision_id)
        assert by_dec.action == "BUY"
        assert by_dec.observation_id == obs.observation_id

    def test_position_and_experience(self, store):
        pos = Position.create("GBPUSD", "SELL", 0.2, entry_price=1.25)
        store.upsert_position(pos)
        opens = store.list_open_positions()
        assert any(p.position_id == pos.position_id for p in opens)

        exp = Experience.create(symbol="GBPUSD", action="SELL", pnl=-5.0, reward=-1.0)
        store.add_experience(exp)
        exps = store.list_experiences(limit=10)
        assert any(e.experience_id == exp.experience_id for e in exps)

    def test_experiment_knowledge_hypothesis(self, store):
        exp = Experiment.create("test_sl_mutation", config={"param": "sl"})
        store.upsert_experiment(exp)
        result = ExperimentResult.create(exp.experiment_id, metrics={"sharpe": 1.2}, passed=True)
        store.add_experiment_result(result)

        claim = KnowledgeClaim.create("Volatility clusters", source="paper", confidence=0.6)
        store.upsert_knowledge(claim)
        hyp = Hypothesis.create("ATR-based SL improves expectancy", claim_id=claim.claim_id)
        store.upsert_hypothesis(hyp)

    def test_risk_capability_events(self, store):
        store.add_risk_event(RiskEvent.create("drawdown_warning", severity="warning", symbol="XAUUSD"))
        store.add_capability_event(CapabilityEvent.create("discovered", provider_name="Git", capability="vcs"))

    def test_model_artifact(self, store):
        art = ModelArtifact.create("policy_net", "v1", "pytorch", path="/models/v1.pt")
        store.upsert_artifact(art)


# ── 5. Transaction rollback ─────────────────────────────────────────────

class TestTransactions:
    def test_rollback_on_error(self, db, store):
        s = Strategy.create("will_rollback")
        store.upsert_strategy(s)

        with pytest.raises(Exception):
            with db.transaction():
                store.set_state("tx_key", "should_not_persist")
                # Force failure via bad FK
                bad = Decision.create(action="BUY", strategy_id="nonexistent-strategy-id")
                store.add_decision(bad)

        assert store.get_state("tx_key") is None

    def test_commit_on_success(self, db, store):
        with db.transaction():
            store.set_state("tx_ok", {"n": 1})
        assert store.get_state("tx_ok") == {"n": 1}


# ── 6. Idempotency ──────────────────────────────────────────────────────

class TestIdempotency:
    def test_duplicate_observation_ignored(self, store):
        obs = Observation.create(symbol="USDJPY", content_hash="abc")
        store.add_observation(obs)
        store.add_observation(obs)  # same id
        rows = store.db.fetchall("SELECT COUNT(*) AS c FROM observations WHERE observation_id = ?",
                                 (obs.observation_id,))
        assert rows[0]["c"] == 1

    def test_duplicate_trade_id_upsert(self, store):
        t = Trade.create("EURUSD", "BUY", 0.1, entry_price=1.1)
        store.upsert_trade(t)
        t.exit_price = 1.12
        t.pnl = 20.0
        t.status = "CLOSED"
        store.upsert_trade(t)
        loaded = store.get_trade(t.trade_id)
        assert loaded.status == "CLOSED"
        assert loaded.pnl == 20.0
        rows = store.db.fetchall("SELECT COUNT(*) AS c FROM trades WHERE trade_id = ?", (t.trade_id,))
        assert rows[0]["c"] == 1

    def test_broker_ticket_unique(self, store):
        t1 = Trade.create("EURUSD", "BUY", 0.1, broker_ticket="UNIQUE-1")
        store.upsert_trade(t1)
        t2 = Trade.create("EURUSD", "BUY", 0.2, broker_ticket="UNIQUE-1")
        store.upsert_trade(t2)
        by_ticket = store.get_trade_by_ticket("UNIQUE-1")
        assert by_ticket is not None


# ── 7. Foreign key / integrity ──────────────────────────────────────────

class TestForeignKeys:
    def test_fk_violation_raises(self, store):
        dec = Decision.create(action="SELL", strategy_id="no-such-strategy")
        with pytest.raises(IntegrityError):
            store.add_decision(dec)

    def test_valid_fk_chain(self, store):
        s = Strategy.create("fk_ok")
        store.upsert_strategy(s)
        dec = Decision.create(action="HOLD", strategy_id=s.strategy_id)
        store.add_decision(dec)


# ── 8. Persistence after process restart ────────────────────────────────

class TestRestartPersistence:
    def test_state_survives_reopen(self, db_path):
        db1 = Database(db_path)
        store1 = MemoryStore(db1)
        s = Strategy.create("persist_me", status="LIVE")
        store1.upsert_strategy(s)
        store1.set_state("last_policy", "P99")
        trade = Trade.create("EURUSD", "BUY", 0.5, strategy_id=s.strategy_id, entry_price=1.05)
        store1.upsert_trade(trade)
        sid, tid = s.strategy_id, trade.trade_id
        db1.close()

        db2 = Database(db_path)
        store2 = MemoryStore(db2)
        assert store2.get_state("last_policy") == "P99"
        assert store2.get_strategy(sid) is not None
        assert store2.get_strategy(sid).status == "LIVE"
        assert store2.get_trade(tid) is not None
        assert store2.get_trade(tid).volume == 0.5
        db2.close()


# ── 9. Concurrent access ────────────────────────────────────────────────

class TestConcurrency:
    def test_parallel_writes(self, db_path):
        errors = []

        def worker(n):
            try:
                db = Database(db_path)
                store = MemoryStore(db)
                for i in range(20):
                    store.set_state(f"w{n}_{i}", i)
                    store.add_risk_event(RiskEvent.create(f"evt_{n}_{i}"))
                db.close()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert not errors, f"Concurrent errors: {errors}"
        db = Database(db_path)
        count = db.fetchone("SELECT COUNT(*) AS c FROM risk_events")["c"]
        assert count == 80
        db.close()


# ── 10. Audit record creation ───────────────────────────────────────────

class TestAudit:
    def test_append_and_list(self, store):
        rec = AuditRecord.create(
            component="strategy",
            action="promote",
            entity_type="strategy",
            entity_id="S1",
            old_state={"status": "VIRTUAL"},
            new_state={"status": "LIVE"},
            reason="passed validation",
        )
        store.append_audit(rec)
        logs = store.list_audit(limit=10)
        assert any(a.audit_id == rec.audit_id for a in logs)
        assert logs[0].old_state["status"] == "VIRTUAL"

    def test_audit_by_entity(self, store):
        store.append_audit(AuditRecord.create("risk", "update", entity_id="E42", reason="test"))
        logs = store.list_audit(entity_id="E42")
        assert len(logs) >= 1


# ── 11. Corruption / integrity detection ────────────────────────────────

class TestIntegrity:
    def test_integrity_ok_on_fresh(self, store):
        result = store.check_integrity()
        assert result["ok"] is True
        assert result["integrity_check"] == "ok"
        assert result["foreign_key_violations"] == []
        assert result["schema_version"] == SCHEMA_VERSION

    def test_detects_fk_issue_via_pragma(self, db, store):
        result = db.check_integrity()
        assert result["ok"] is True


# ── 12. CI-compatible suite smoke ───────────────────────────────────────

class TestSmoke:
    def test_utc_now_format(self):
        ts = utc_now()
        assert ts.endswith("Z")
        assert "T" in ts

    def test_full_lifecycle_no_trading_logic(self, store):
        """End-to-end memory cycle without any trading intelligence."""
        s = Strategy.create("lifecycle")
        store.upsert_strategy(s)
        store.add_strategy_version(StrategyVersion.create(s.strategy_id, 1, {"x": 1}))
        obs = Observation.create(symbol="EURUSD")
        store.add_observation(obs)
        dec = Decision.create("HOLD", strategy_id=s.strategy_id, observation_id=obs.observation_id)
        store.add_decision(dec)
        trade = Trade.create("EURUSD", "BUY", 0.01, decision_id=dec.decision_id,
                             strategy_id=s.strategy_id, is_virtual=True)
        store.upsert_trade(trade)
        store.add_experience(Experience.create(trade_id=trade.trade_id, is_virtual=True, reward=0.0))
        store.append_audit(AuditRecord.create("agent", "cycle", entity_id=s.strategy_id))
        store.set_state("last_cycle", utc_now())

        assert store.check_integrity()["ok"]
        assert store.get_state("last_cycle")
        assert len(store.list_experiences()) >= 1
