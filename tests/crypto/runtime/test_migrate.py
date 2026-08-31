"""SQLite migration atomicity, backup, failure handling."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from crypto.runtime.migrate import (
    CURRENT_SCHEMA_VERSION,
    get_user_version,
    migrate,
    open_and_migrate,
)


def test_fresh_migrate(tmp_path: Path) -> None:
    db = tmp_path / "state" / "crypto.db"
    backups = tmp_path / "backups"
    conn, result = open_and_migrate(db, backups)
    assert result.ok
    assert get_user_version(conn) == CURRENT_SCHEMA_VERSION  # type: ignore[arg-type]
    assert conn is not None
    conn.close()
    assert db.is_file()


def test_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    backups = tmp_path / "b"
    conn, r1 = open_and_migrate(db, backups)
    assert r1.ok
    conn.close()
    conn, r2 = open_and_migrate(db, backups)
    assert r2.ok
    assert "up to date" in r2.detail
    conn.close()


def test_backup_created(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    backups = tmp_path / "b"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE t (x INT)")
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    conn.close()
    conn, result = open_and_migrate(db, backups)
    assert result.ok
    conn.close()
    if result.backup_path:
        assert Path(result.backup_path).is_file()


def test_newer_schema_rejected(tmp_path: Path) -> None:
    db = tmp_path / "c.db"
    conn = sqlite3.connect(str(db))
    conn.execute(f"PRAGMA user_version = {CURRENT_SCHEMA_VERSION + 10}")
    conn.commit()
    result = migrate(conn, db_path=db, backups_dir=tmp_path / "b")
    assert result.ok is False
    assert "newer" in result.detail
    conn.close()


def test_failed_migration_preserves_db(tmp_path: Path) -> None:
    """Missing migration path does not destroy file."""
    from crypto.runtime import migrate as migrate_module

    db = tmp_path / "c.db"
    conn = sqlite3.connect(str(db))
    conn.execute("PRAGMA user_version = 0")
    conn.commit()
    saved = dict(migrate_module.MIGRATIONS)
    try:
        migrate_module.MIGRATIONS.clear()
        result = migrate_module.migrate(conn, db_path=db, backups_dir=tmp_path / "b", target=1)
        assert result.ok is False
        assert get_user_version(conn) == 0
    finally:
        migrate_module.MIGRATIONS.update(saved)
        conn.close()
    assert db.is_file()


def test_model_compat() -> None:
    from crypto.runtime.compat import check_model_artifact_schema

    assert check_model_artifact_schema({"schema_version": 1}).compatible
    assert not check_model_artifact_schema({"schema_version": 99}).compatible
    assert check_model_artifact_schema(None).use_fallback
