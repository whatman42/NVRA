"""Typed repository / MemoryStore for all domain tables.

Idempotent inserts use INSERT OR IGNORE / ON CONFLICT where appropriate.
Audit log is append-only (no update/delete methods).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .database import Database, IntegrityError, utc_now
from .models import (
    AgentState, AuditRecord, CapabilityEvent, Decision, Experience,
    Experiment, ExperimentResult, Hypothesis, KnowledgeClaim,
    ModelArtifact, Observation, Position, RiskEvent, Strategy,
    StrategyVersion, Trade,
)
from .models_core import _dumps, _loads


class _MemoryStoreCore:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ── Agent State ──────────────────────────────────────────────────────

    def set_state(self, key: str, value: Any) -> None:
        self.db.execute(
            """INSERT INTO agent_state (key, value_json, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
            (key, _dumps(value), utc_now()),
        )

    def get_state(self, key: str, default: Any = None) -> Any:
        row = self.db.fetchone("SELECT value_json FROM agent_state WHERE key = ?", (key,))
        if row is None:
            return default
        return _loads(row["value_json"])

    # ── Strategies ───────────────────────────────────────────────────────

    def upsert_strategy(self, s: Strategy) -> None:
        self.db.execute(
            """INSERT INTO strategies (strategy_id, name, status, parent_id, generation, created_at, updated_at, metadata_json)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(strategy_id) DO UPDATE SET
                 name=excluded.name, status=excluded.status, parent_id=excluded.parent_id,
                 generation=excluded.generation, updated_at=excluded.updated_at, metadata_json=excluded.metadata_json""",
            (s.strategy_id, s.name, s.status, s.parent_id, s.generation,
             s.created_at, s.updated_at or utc_now(), _dumps(s.metadata)),
        )

    def get_strategy(self, strategy_id: str) -> Optional[Strategy]:
        row = self.db.fetchone("SELECT * FROM strategies WHERE strategy_id = ?", (strategy_id,))
        return self._row_to_strategy(row) if row else None

    def list_strategies(self, status: Optional[str] = None) -> list[Strategy]:
        if status:
            rows = self.db.fetchall("SELECT * FROM strategies WHERE status = ? ORDER BY created_at", (status,))
        else:
            rows = self.db.fetchall("SELECT * FROM strategies ORDER BY created_at")
        return [self._row_to_strategy(r) for r in rows]

    def _row_to_strategy(self, row) -> Strategy:
        return Strategy(
            strategy_id=row["strategy_id"], name=row["name"], status=row["status"],
            parent_id=row["parent_id"], generation=row["generation"],
            created_at=row["created_at"], updated_at=row["updated_at"],
            metadata=_loads(row["metadata_json"]),
        )

    def add_strategy_version(self, sv: StrategyVersion) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO strategy_versions
               (version_id, strategy_id, version_num, genome_json, lineage_json, created_at)
               VALUES (?,?,?,?,?,?)""",
            (sv.version_id, sv.strategy_id, sv.version_num,
             _dumps(sv.genome), _dumps(sv.lineage), sv.created_at),
        )

    def get_strategy_versions(self, strategy_id: str) -> list[StrategyVersion]:
        rows = self.db.fetchall(
            "SELECT * FROM strategy_versions WHERE strategy_id = ? ORDER BY version_num",
            (strategy_id,),
        )
        return [
            StrategyVersion(
                version_id=r["version_id"], strategy_id=r["strategy_id"],
                version_num=r["version_num"], genome=_loads(r["genome_json"]),
                lineage=_loads(r["lineage_json"]), created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Observations ─────────────────────────────────────────────────────

    def add_observation(self, o: Observation) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO observations
               (observation_id, timestamp, symbol, timeframe, market_state_json, features_json,
                regime, source, content_hash, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (o.observation_id, o.timestamp, o.symbol, o.timeframe,
             _dumps(o.market_state), _dumps(o.features), o.regime, o.source,
             o.content_hash, o.created_at),
        )

    def get_observation(self, observation_id: str) -> Optional[Observation]:
        row = self.db.fetchone("SELECT * FROM observations WHERE observation_id = ?", (observation_id,))
        if not row:
            return None
        return Observation(
            observation_id=row["observation_id"], timestamp=row["timestamp"],
            symbol=row["symbol"], timeframe=row["timeframe"],
            market_state=_loads(row["market_state_json"]),
            features=_loads(row["features_json"]),
            regime=row["regime"], source=row["source"],
            content_hash=row["content_hash"], created_at=row["created_at"],
        )

    # ── Decisions ────────────────────────────────────────────────────────

    def add_decision(self, d: Decision) -> None:
        self.db.execute(
            """INSERT OR IGNORE INTO decisions
               (decision_id, timestamp, symbol, timeframe, action, strategy_id, strategy_version,
                policy_version, volume, sl, tp, confidence, regime, reasoning_json,
                observation_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (d.decision_id, d.timestamp, d.symbol, d.timeframe, d.action,
             d.strategy_id, d.strategy_version, d.policy_version, d.volume,
             d.sl, d.tp, d.confidence, d.regime, _dumps(d.reasoning),
             d.observation_id, d.created_at),
        )

    def get_decision(self, decision_id: str) -> Optional[Decision]:
        row = self.db.fetchone("SELECT * FROM decisions WHERE decision_id = ?", (decision_id,))
        if not row:
            return None
        return Decision(
            decision_id=row["decision_id"], timestamp=row["timestamp"],
            action=row["action"], symbol=row["symbol"], timeframe=row["timeframe"],
            strategy_id=row["strategy_id"], strategy_version=row["strategy_version"],
            policy_version=row["policy_version"], volume=row["volume"],
            sl=row["sl"], tp=row["tp"], confidence=row["confidence"],
            regime=row["regime"], reasoning=_loads(row["reasoning_json"]),
            observation_id=row["observation_id"], created_at=row["created_at"],
        )

    # ── Trades ───────────────────────────────────────────────────────────

    def upsert_trade(self, t: Trade) -> None:
        self.db.execute(
            """INSERT INTO trades
               (trade_id, decision_id, symbol, side, volume, entry_price, exit_price, sl, tp,
                opened_at, closed_at, pnl, fees, spread, slippage, mae, mfe, holding_time_sec,
                status, broker_ticket, strategy_id, strategy_version, is_virtual, metadata_json,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(trade_id) DO UPDATE SET
                 exit_price=excluded.exit_price, closed_at=excluded.closed_at, pnl=excluded.pnl,
                 fees=excluded.fees, status=excluded.status, mae=excluded.mae, mfe=excluded.mfe,
                 holding_time_sec=excluded.holding_time_sec, updated_at=excluded.updated_at,
                 metadata_json=excluded.metadata_json""",
            (t.trade_id, t.decision_id, t.symbol, t.side, t.volume, t.entry_price, t.exit_price,
             t.sl, t.tp, t.opened_at, t.closed_at, t.pnl, t.fees, t.spread, t.slippage,
             t.mae, t.mfe, t.holding_time_sec, t.status, t.broker_ticket, t.strategy_id,
             t.strategy_version, int(t.is_virtual), _dumps(t.metadata),
             t.created_at, t.updated_at or utc_now()),
        )

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        row = self.db.fetchone("SELECT * FROM trades WHERE trade_id = ?", (trade_id,))
        return self._row_to_trade(row) if row else None

    def get_trade_by_ticket(self, broker_ticket: str) -> Optional[Trade]:
        row = self.db.fetchone("SELECT * FROM trades WHERE broker_ticket = ?", (broker_ticket,))
        return self._row_to_trade(row) if row else None
