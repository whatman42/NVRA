"""Extended MemoryStore methods."""
from __future__ import annotations
from typing import Any, Optional, List

from .models import (
    AuditRecord, CapabilityEvent, Decision, Experience,
    Experiment, ExperimentResult, Hypothesis, KnowledgeClaim,
    ModelArtifact, Observation, Position, RiskEvent,
    Strategy, StrategyVersion, Trade,
)
from .database import utc_now
from .models_core import _dumps, _loads

class _MemoryStoreExt:
    def list_trades(self, status: Optional[str] = None, is_virtual: Optional[bool] = None) -> list[Trade]:
        clauses, params = [], []
        if status is not None:
            clauses.append("status = ?"); params.append(status)
        if is_virtual is not None:
            clauses.append("is_virtual = ?"); params.append(int(is_virtual))
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self.db.fetchall(f"SELECT * FROM trades {where} ORDER BY created_at", params)
        return [self._row_to_trade(r) for r in rows]

    def _row_to_trade(self, row) -> Trade:
        return Trade(
            trade_id=row["trade_id"], decision_id=row["decision_id"], symbol=row["symbol"],
            side=row["side"], volume=row["volume"], entry_price=row["entry_price"],
            exit_price=row["exit_price"], sl=row["sl"], tp=row["tp"],
            opened_at=row["opened_at"], closed_at=row["closed_at"], pnl=row["pnl"],
            fees=row["fees"] or 0, spread=row["spread"], slippage=row["slippage"],
            mae=row["mae"], mfe=row["mfe"], holding_time_sec=row["holding_time_sec"],
            status=row["status"], broker_ticket=row["broker_ticket"],
            strategy_id=row["strategy_id"], strategy_version=row["strategy_version"],
            is_virtual=bool(row["is_virtual"]), metadata=_loads(row["metadata_json"]),
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    # ── Positions ────────────────────────────────────────────────────────

    def upsert_position(self, p: Position) -> None:
        self.db.execute(
            """INSERT INTO positions
               (position_id, symbol, side, volume, entry_price, current_price, sl, tp,
                unrealized_pnl, broker_ticket, strategy_id, opened_at, updated_at, status,
                is_virtual, metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(position_id) DO UPDATE SET
                 current_price=excluded.current_price, unrealized_pnl=excluded.unrealized_pnl,
                 sl=excluded.sl, tp=excluded.tp, status=excluded.status,
                 updated_at=excluded.updated_at, volume=excluded.volume,
                 metadata_json=excluded.metadata_json""",
            (p.position_id, p.symbol, p.side, p.volume, p.entry_price, p.current_price,
             p.sl, p.tp, p.unrealized_pnl, p.broker_ticket, p.strategy_id,
             p.opened_at, p.updated_at or utc_now(), p.status,
             int(p.is_virtual), _dumps(p.metadata)),
        )

    def list_open_positions(self, is_virtual: Optional[bool] = None) -> list[Position]:
        if is_virtual is not None:
            rows = self.db.fetchall(
                "SELECT * FROM positions WHERE status = 'OPEN' AND is_virtual = ?",
                (int(is_virtual),),
            )
        else:
            rows = self.db.fetchall("SELECT * FROM positions WHERE status = 'OPEN'")
        return [self._row_to_position(r) for r in rows]

    def _row_to_position(self, row) -> Position:
        return Position(
            position_id=row["position_id"], symbol=row["symbol"], side=row["side"],
            volume=row["volume"], entry_price=row["entry_price"],
            current_price=row["current_price"], sl=row["sl"], tp=row["tp"],
            unrealized_pnl=row["unrealized_pnl"], broker_ticket=row["broker_ticket"],
            strategy_id=row["strategy_id"], opened_at=row["opened_at"],
            updated_at=row["updated_at"], status=row["status"],
            is_virtual=bool(row["is_virtual"]), metadata=_loads(row["metadata_json"]),
        )

    # ── Experiences ──────────────────────────────────────────────────────

    def add_experience(self, e: Experience) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO experiences
               (experience_id, timestamp, symbol, timeframe, market_state_json, features_json,
                regime, strategy_id, strategy_version, action, entry_price, exit_price, sl, tp,
                position_size, fees, spread, slippage, mae, mfe, holding_time_sec, pnl, reward,
                outcome, policy_version, trade_id, is_virtual, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (e.experience_id, e.timestamp, e.symbol, e.timeframe,
             _dumps(e.market_state), _dumps(e.features), e.regime,
             e.strategy_id, e.strategy_version, e.action, e.entry_price, e.exit_price,
             e.sl, e.tp, e.position_size, e.fees, e.spread, e.slippage, e.mae, e.mfe,
             e.holding_time_sec, e.pnl, e.reward, e.outcome, e.policy_version,
             e.trade_id, int(e.is_virtual), e.created_at),
        )

    def list_experiences(self, limit: int = 100) -> list[Experience]:
        rows = self.db.fetchall(
            "SELECT * FROM experiences ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [
            Experience(
                experience_id=r["experience_id"], timestamp=r["timestamp"],
                symbol=r["symbol"], timeframe=r["timeframe"],
                market_state=_loads(r["market_state_json"]),
                features=_loads(r["features_json"]),
                regime=r["regime"], strategy_id=r["strategy_id"],
                strategy_version=r["strategy_version"], action=r["action"],
                entry_price=r["entry_price"], exit_price=r["exit_price"],
                sl=r["sl"], tp=r["tp"], position_size=r["position_size"],
                fees=r["fees"], spread=r["spread"], slippage=r["slippage"],
                mae=r["mae"], mfe=r["mfe"], holding_time_sec=r["holding_time_sec"],
                pnl=r["pnl"], reward=r["reward"], outcome=r["outcome"],
                policy_version=r["policy_version"], trade_id=r["trade_id"],
                is_virtual=bool(r["is_virtual"]), created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Experiments ──────────────────────────────────────────────────────

    def upsert_experiment(self, e: Experiment) -> None:
        self.db.execute(
            """INSERT INTO experiments
               (experiment_id, name, hypothesis_id, status, priority, config_json,
                created_at, updated_at, started_at, finished_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(experiment_id) DO UPDATE SET
                 status=excluded.status, priority=excluded.priority, config_json=excluded.config_json,
                 updated_at=excluded.updated_at, started_at=excluded.started_at,
                 finished_at=excluded.finished_at""",
            (e.experiment_id, e.name, e.hypothesis_id, e.status, e.priority,
             _dumps(e.config), e.created_at, e.updated_at or utc_now(),
             e.started_at, e.finished_at),
        )

    def add_experiment_result(self, r: ExperimentResult) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO experiment_results
               (result_id, experiment_id, metrics_json, passed, notes, created_at)
               VALUES (?,?,?,?,?,?)""",
            (r.result_id, r.experiment_id, _dumps(r.metrics),
             None if r.passed is None else int(r.passed), r.notes, r.created_at),
        )

    # ── Knowledge ────────────────────────────────────────────────────────

    def upsert_knowledge(self, k: KnowledgeClaim) -> None:
        self.db.execute(
            """INSERT INTO knowledge_claims
               (claim_id, source, url, title, author, publication_date, retrieval_date,
                content_hash, claim, evidence, methodology, dataset, limitations,
                confidence, status, validation_status, metadata_json, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(claim_id) DO UPDATE SET
                 status=excluded.status, validation_status=excluded.validation_status,
                 confidence=excluded.confidence, updated_at=excluded.updated_at,
                 metadata_json=excluded.metadata_json""",
            (k.claim_id, k.source, k.url, k.title, k.author, k.publication_date,
             k.retrieval_date, k.content_hash, k.claim, k.evidence, k.methodology,
             k.dataset, k.limitations, k.confidence, k.status, k.validation_status,
             _dumps(k.metadata), k.created_at, k.updated_at or utc_now()),
        )

    def upsert_hypothesis(self, h: Hypothesis) -> None:
        self.db.execute(
            """INSERT INTO hypotheses
               (hypothesis_id, claim_id, statement, status, confidence, experiment_id,
                created_at, updated_at, metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(hypothesis_id) DO UPDATE SET
                 status=excluded.status, confidence=excluded.confidence,
                 experiment_id=excluded.experiment_id, updated_at=excluded.updated_at,
                 metadata_json=excluded.metadata_json""",
            (h.hypothesis_id, h.claim_id, h.statement, h.status, h.confidence,
             h.experiment_id, h.created_at, h.updated_at or utc_now(), _dumps(h.metadata)),
        )

    # ── Risk / Capability events ─────────────────────────────────────────

    def add_risk_event(self, e: RiskEvent) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO risk_events
               (event_id, timestamp, event_type, severity, symbol, details_json, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (e.event_id, e.timestamp, e.event_type, e.severity, e.symbol,
             _dumps(e.details), e.created_at),
        )

    def add_capability_event(self, e: CapabilityEvent) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO capability_events
               (event_id, timestamp, provider_id, provider_name, capability, event_type,
                details_json, created_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (e.event_id, e.timestamp, e.provider_id, e.provider_name, e.capability,
             e.event_type, _dumps(e.details), e.created_at),
        )

    # ── Audit (append-only) ──────────────────────────────────────────────

    def append_audit(self, a: AuditRecord) -> None:
        self.db.execute(
            """INSERT INTO audit_log
               (audit_id, timestamp, component, action, entity_type, entity_id,
                old_state_json, new_state_json, reason, evidence_json, actor, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (a.audit_id, a.timestamp, a.component, a.action, a.entity_type, a.entity_id,
             _dumps(a.old_state) if a.old_state is not None else None,
             _dumps(a.new_state) if a.new_state is not None else None,
             a.reason, _dumps(a.evidence) if a.evidence is not None else None,
             a.actor, a.created_at),
        )

    def list_audit(self, limit: int = 50, entity_id: Optional[str] = None) -> list[AuditRecord]:
        if entity_id:
            rows = self.db.fetchall(
                "SELECT * FROM audit_log WHERE entity_id = ? ORDER BY timestamp DESC LIMIT ?",
                (entity_id, limit),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            )
        return [
            AuditRecord(
                audit_id=r["audit_id"], timestamp=r["timestamp"],
                component=r["component"], action=r["action"],
                entity_type=r["entity_type"], entity_id=r["entity_id"],
                old_state=_loads(r["old_state_json"]) if r["old_state_json"] else None,
                new_state=_loads(r["new_state_json"]) if r["new_state_json"] else None,
                reason=r["reason"],
                evidence=_loads(r["evidence_json"]) if r["evidence_json"] else None,
                actor=r["actor"], created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Model artifacts ──────────────────────────────────────────────────

    def upsert_artifact(self, a: ModelArtifact) -> None:
        self.db.execute(
            """INSERT INTO model_artifacts
               (artifact_id, name, version, artifact_type, path, checksum, metrics_json,
                status, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(name, version) DO UPDATE SET
                 path=excluded.path, checksum=excluded.checksum, metrics_json=excluded.metrics_json,
                 status=excluded.status, updated_at=excluded.updated_at""",
            (a.artifact_id, a.name, a.version, a.artifact_type, a.path, a.checksum,
             _dumps(a.metrics), a.status, a.created_at, a.updated_at or utc_now()),
        )

    # ── Integrity ────────────────────────────────────────────────────────

    def check_integrity(self) -> dict:
        return self.db.check_integrity()
