"""SQLite crash-safety helpers for execution / recovery state."""

from __future__ import annotations

import sqlite3
from contextlib import suppress
from pathlib import Path

from crypto.recovery.config import RecoveryConfig
from crypto.recovery.events import make_event


class StorageHealth:
    OK = "OK"
    CORRUPT = "CORRUPT"
    MISSING = "MISSING"


def open_hardened_db(path: str | Path, config: RecoveryConfig | None = None) -> sqlite3.Connection:
    cfg = config or RecoveryConfig()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=cfg.sqlite_busy_timeout_ms / 1000.0)
    conn.row_factory = sqlite3.Row
    if cfg.use_wal:
        with suppress(sqlite3.Error):
            conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={cfg.sqlite_busy_timeout_ms}")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def integrity_check(conn: sqlite3.Connection) -> str:
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row is None:
            return StorageHealth.CORRUPT
        result = str(row[0]).lower()
        return StorageHealth.OK if result == "ok" else StorageHealth.CORRUPT
    except sqlite3.Error:
        return StorageHealth.CORRUPT


def ensure_recovery_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS recovery_checkpoint (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at_ms INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS recovery_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms INTEGER NOT NULL,
            event TEXT NOT NULL,
            component_id TEXT,
            detail TEXT,
            level INTEGER DEFAULT 0
        );
        """
    )
    conn.commit()






