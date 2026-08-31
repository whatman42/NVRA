"""Versioned SQLite schema migration — atomic, idempotent, crash-safe.

Uses PRAGMA user_version. Never silently deletes/recreates the database.
On failure: leave DB intact, signal SAFE MODE (caller decides).
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

# Target schema version for this application release
CURRENT_SCHEMA_VERSION = 1

MigrationFn = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True, slots=True)
class MigrationResult:
    ok: bool
    from_version: int
    to_version: int
    detail: str = ""
    backup_path: str | None = None


def get_user_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def set_user_version(conn: sqlite3.Connection, version: int) -> None:
    # PRAGMA does not support parameterized version in all builds — int only
    if version < 0 or version > 2_000_000_000:
        raise ValueError("invalid schema version")
    conn.execute(f"PRAGMA user_version = {int(version)}")


def backup_database(db_path: Path, backups_dir: Path) -> Path:
    backups_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    dest = backups_dir / f"{db_path.stem}_vbackup_{ts}{db_path.suffix}"
    shutil.copy2(db_path, dest)
    # Also copy WAL/SHM if present
    for suffix in ("-wal", "-shm"):
        side = Path(str(db_path) + suffix)
        if side.is_file():
            shutil.copy2(side, Path(str(dest) + suffix))
    return dest


# --- versioned migrations (0 → 1, 1 → 2, ...) ---


def _migrate_0_to_1(conn: sqlite3.Connection) -> None:
    """Baseline recovery/execution support tables (idempotent)."""
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
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at_ms INTEGER NOT NULL,
            detail TEXT
        );
        """
    )


MIGRATIONS: dict[int, MigrationFn] = {
    # key = version AFTER applying this migration
    1: _migrate_0_to_1,
}


def migrate(
    conn: sqlite3.Connection,
    *,
    db_path: Path | None = None,
    backups_dir: Path | None = None,
    target: int = CURRENT_SCHEMA_VERSION,
) -> MigrationResult:
    """Apply pending migrations up to *target*.

    On failure: does not advance user_version; returns ok=False.
    """
    current = get_user_version(conn)
    if current > target:
        return MigrationResult(
            ok=False,
            from_version=current,
            to_version=target,
            detail=f"database schema {current} newer than app {target}",
        )
    if current == target:
        return MigrationResult(
            ok=True, from_version=current, to_version=target, detail="up to date"
        )

    backup_path: str | None = None
    if db_path is not None and db_path.is_file() and backups_dir is not None:
        try:
            backup_path = str(backup_database(db_path, backups_dir))
        except OSError as exc:
            return MigrationResult(
                ok=False,
                from_version=current,
                to_version=target,
                detail=f"backup failed: {exc}",
            )

    from_v = current
    try:
        for next_v in range(current + 1, target + 1):
            fn = MIGRATIONS.get(next_v)
            if fn is None:
                return MigrationResult(
                    ok=False,
                    from_version=from_v,
                    to_version=next_v,
                    detail=f"missing migration for version {next_v}",
                    backup_path=backup_path,
                )
            # Each step in a transaction
            try:
                conn.execute("BEGIN")
                fn(conn)
                set_user_version(conn, next_v)
                conn.execute(
                    "INSERT OR REPLACE INTO schema_migrations (version, applied_at_ms, detail) "
                    "VALUES (?, ?, ?)",
                    (next_v, int(time.time() * 1000), f"migrated to {next_v}"),
                )
                conn.execute("COMMIT")
            except Exception:
                with suppress(sqlite3.Error):
                    conn.execute("ROLLBACK")
                raise
        return MigrationResult(
            ok=True,
            from_version=from_v,
            to_version=target,
            detail="migrated",
            backup_path=backup_path,
        )
    except Exception as exc:  # noqa: BLE001
        return MigrationResult(
            ok=False,
            from_version=from_v,
            to_version=target,
            detail=f"migration failed: {type(exc).__name__}: {exc}",
            backup_path=backup_path,
        )


def open_and_migrate(
    db_path: Path,
    backups_dir: Path,
    *,
    busy_timeout_ms: int = 5000,
) -> tuple[sqlite3.Connection | None, MigrationResult]:
    """Open DB, run migrations, return (conn, result).

    On failure conn may still be open for diagnostics; caller must not trade.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=busy_timeout_ms / 1000.0)
    conn.row_factory = sqlite3.Row
    with suppress(sqlite3.Error):
        conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        conn.execute("PRAGMA journal_mode=WAL")
    # Integrity first
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row and str(row[0]).lower() != "ok":
            return conn, MigrationResult(
                ok=False,
                from_version=-1,
                to_version=CURRENT_SCHEMA_VERSION,
                detail="integrity_check failed",
            )
    except sqlite3.Error as exc:
        return conn, MigrationResult(
            ok=False,
            from_version=-1,
            to_version=CURRENT_SCHEMA_VERSION,
            detail=f"integrity error: {exc}",
        )
    result = migrate(conn, db_path=db_path, backups_dir=backups_dir)
    return conn, result
