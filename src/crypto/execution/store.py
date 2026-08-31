"""SQLite persistence for execution state (crash recovery)."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from crypto.execution.models import ExecutionMode, ExecutionRecord, Fill, now_ms
from crypto.execution.states import OrderState
from crypto.risk.models import Side


class ExecutionStore:
    """Lightweight SQLite store. Secrets are never written."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS executions (
                execution_id TEXT PRIMARY KEY,
                client_order_id TEXT NOT NULL,
                exchange_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                requested_quantity REAL NOT NULL,
                requested_price REAL,
                allowed_quantity REAL NOT NULL,
                allowed_notional REAL NOT NULL,
                state TEXT NOT NULL,
                exchange_order_id TEXT,
                filled_quantity REAL NOT NULL DEFAULT 0,
                remaining_quantity REAL NOT NULL DEFAULT 0,
                average_fill_price REAL,
                fees_total REAL NOT NULL DEFAULT 0,
                fee_currency TEXT,
                fills_json TEXT NOT NULL DEFAULT '[]',
                last_error TEXT,
                created_at_ms INTEGER NOT NULL,
                updated_at_ms INTEGER NOT NULL,
                strategy_id TEXT,
                correlation_id TEXT,
                mode TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_exec_client
                ON executions(client_order_id);
            CREATE INDEX IF NOT EXISTS idx_exec_state
                ON executions(state);
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_ms INTEGER NOT NULL,
                correlation_id TEXT,
                execution_id TEXT,
                event TEXT NOT NULL,
                detail TEXT,
                state TEXT
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def save(self, rec: ExecutionRecord) -> None:
        fills_json = json.dumps(
            [
                {
                    "fill_id": f.fill_id,
                    "quantity": f.quantity,
                    "price": f.price,
                    "fee_amount": f.fee_amount,
                    "fee_currency": f.fee_currency,
                    "timestamp_ms": f.timestamp_ms,
                }
                for f in rec.fills
            ]
        )
        self._conn.execute(
            """
            INSERT INTO executions (
                execution_id, client_order_id, exchange_id, account_id, symbol,
                side, order_type, requested_quantity, requested_price,
                allowed_quantity, allowed_notional, state, exchange_order_id,
                filled_quantity, remaining_quantity, average_fill_price,
                fees_total, fee_currency, fills_json, last_error,
                created_at_ms, updated_at_ms, strategy_id, correlation_id, mode
            ) VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            ON CONFLICT(execution_id) DO UPDATE SET
                state=excluded.state,
                exchange_order_id=excluded.exchange_order_id,
                filled_quantity=excluded.filled_quantity,
                remaining_quantity=excluded.remaining_quantity,
                average_fill_price=excluded.average_fill_price,
                fees_total=excluded.fees_total,
                fee_currency=excluded.fee_currency,
                fills_json=excluded.fills_json,
                last_error=excluded.last_error,
                updated_at_ms=excluded.updated_at_ms
            """,
            (
                rec.execution_id,
                rec.client_order_id,
                rec.exchange_id,
                rec.account_id,
                rec.symbol,
                rec.side.name,
                rec.order_type,
                rec.requested_quantity,
                rec.requested_price,
                rec.allowed_quantity,
                rec.allowed_notional,
                rec.state.name,
                rec.exchange_order_id,
                rec.filled_quantity,
                rec.remaining_quantity,
                rec.average_fill_price,
                rec.fees_total,
                rec.fee_currency,
                fills_json,
                rec.last_error,
                rec.created_at_ms,
                rec.updated_at_ms,
                rec.strategy_id,
                rec.correlation_id,
                rec.mode.name,
            ),
        )
        self._conn.commit()

    def get(self, execution_id: str) -> ExecutionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM executions WHERE execution_id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def get_by_client_order_id(self, client_order_id: str) -> ExecutionRecord | None:
        row = self._conn.execute(
            "SELECT * FROM executions WHERE client_order_id = ? ORDER BY created_at_ms DESC LIMIT 1",
            (client_order_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_record(row)

    def list_active(self) -> list[ExecutionRecord]:
        rows = self._conn.execute(
            """
            SELECT * FROM executions WHERE state NOT IN
            ('FILLED', 'CANCELLED', 'REJECTED', 'FAILED')
            ORDER BY created_at_ms
            """
        ).fetchall()
        return [self._row_to_record(r) for r in rows]

    def list_all(self) -> list[ExecutionRecord]:
        rows = self._conn.execute("SELECT * FROM executions ORDER BY created_at_ms").fetchall()
        return [self._row_to_record(r) for r in rows]

    def audit(
        self,
        *,
        correlation_id: str,
        execution_id: str,
        event: str,
        detail: str,
        state: str | None = None,
    ) -> None:
        # Never accept secrets — callers must sanitize
        self._conn.execute(
            """
            INSERT INTO audit (timestamp_ms, correlation_id, execution_id, event, detail, state)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (now_ms(), correlation_id, execution_id, event, detail[:2000], state),
        )
        self._conn.commit()

    def audit_events(self, execution_id: str) -> list[dict[str, object]]:
        rows = self._conn.execute(
            "SELECT * FROM audit WHERE execution_id = ? ORDER BY id",
            (execution_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _row_to_record(self, row: sqlite3.Row) -> ExecutionRecord:
        fills_raw = json.loads(row["fills_json"] or "[]")
        fills = [
            Fill(
                fill_id=str(f["fill_id"]),
                quantity=float(f["quantity"]),
                price=float(f["price"]),
                fee_amount=f.get("fee_amount"),
                fee_currency=f.get("fee_currency"),
                timestamp_ms=int(f["timestamp_ms"]),
            )
            for f in fills_raw
        ]
        return ExecutionRecord(
            execution_id=row["execution_id"],
            client_order_id=row["client_order_id"],
            exchange_id=row["exchange_id"],
            account_id=row["account_id"],
            symbol=row["symbol"],
            side=Side[row["side"]],
            order_type=row["order_type"],
            requested_quantity=row["requested_quantity"],
            requested_price=row["requested_price"],
            allowed_quantity=row["allowed_quantity"],
            allowed_notional=row["allowed_notional"],
            state=OrderState[row["state"]],
            exchange_order_id=row["exchange_order_id"],
            filled_quantity=row["filled_quantity"],
            remaining_quantity=row["remaining_quantity"],
            average_fill_price=row["average_fill_price"],
            fees_total=row["fees_total"],
            fee_currency=row["fee_currency"],
            fills=fills,
            last_error=row["last_error"],
            created_at_ms=row["created_at_ms"],
            updated_at_ms=row["updated_at_ms"],
            strategy_id=row["strategy_id"] or "",
            correlation_id=row["correlation_id"] or "",
            mode=ExecutionMode[row["mode"]],
        )
