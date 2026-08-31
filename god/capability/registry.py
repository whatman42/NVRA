"""Capability Registry — in-memory + optional SQLite persistence.

Stores discovered providers so the agent can query availability and
select tools adaptively. Designed to be dynamic: rescan updates
existing entries rather than requiring a full restart.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .models import Capability, CapabilityProvider, CapabilityType


class CapabilityRegistry:
    """Thread-safe registry of discovered capabilities."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self._lock = threading.RLock()
        self._providers: dict[str, CapabilityProvider] = {}  # provider_id -> provider
        self._by_capability: dict[CapabilityType, list[str]] = {}
        self._by_name: dict[str, str] = {}  # name.lower() -> provider_id
        self._db_path = Path(db_path) if db_path else None
        self._last_scan: float = 0.0
        if self._db_path:
            self._init_db()
            self._load_from_db()

    # ── Persistence ──────────────────────────────────────────────────────

    def close(self) -> None:
        """Release handles before TemporaryDirectory cleanup (Windows)."""
        return

    def _open_db(self) -> sqlite3.Connection:
        assert self._db_path is not None
        return sqlite3.connect(str(self._db_path), timeout=30.0)

    def _init_db(self) -> None:
        assert self._db_path is not None
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = self._open_db()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS capability_providers (
                    provider_id   TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    capability    TEXT NOT NULL,
                    available     INTEGER NOT NULL,
                    executable    TEXT,
                    version       TEXT,
                    path          TEXT,
                    interface     TEXT,
                    health        TEXT,
                    latency_ms    REAL,
                    success_rate  REAL,
                    last_checked  REAL,
                    last_used     REAL,
                    metadata_json TEXT,
                    failure_count INTEGER,
                    usage_count   INTEGER
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cap_type ON capability_providers(capability)"
            )
            conn.commit()

        finally:
            conn.close()
    def _load_from_db(self) -> None:
        if not self._db_path or not self._db_path.exists():
            return
        conn = self._open_db()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM capability_providers").fetchall()
        finally:
            conn.close()
        for row in rows:
            meta = json.loads(row["metadata_json"] or "{}")
            p = CapabilityProvider(
                provider_id=row["provider_id"],
                name=row["name"],
                capability=CapabilityType(row["capability"]),
                available=bool(row["available"]),
                executable=row["executable"],
                version=row["version"],
                path=row["path"],
                interface=row["interface"],
                health=row["health"] or "unknown",
                latency_ms=row["latency_ms"],
                success_rate=row["success_rate"] if row["success_rate"] is not None else 1.0,
                last_checked=row["last_checked"] or time.time(),
                last_used=row["last_used"],
                metadata=meta,
                failure_count=row["failure_count"] or 0,
                usage_count=row["usage_count"] or 0,
            )
            self._register(p, persist=False)

    def _persist(self, p: CapabilityProvider) -> None:
        if not self._db_path:
            return
        conn = self._open_db()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO capability_providers (
                    provider_id, name, capability, available, executable,
                    version, path, interface, health, latency_ms, success_rate,
                    last_checked, last_used, metadata_json, failure_count, usage_count
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    p.provider_id,
                    p.name,
                    p.capability.value,
                    int(p.available),
                    p.executable,
                    p.version,
                    p.path,
                    p.interface,
                    p.health,
                    p.latency_ms,
                    p.success_rate,
                    p.last_checked,
                    p.last_used,
                    json.dumps(p.metadata),
                    p.failure_count,
                    p.usage_count,
                ),
            )
            conn.commit()

        finally:
            conn.close()
    # ── Registration ─────────────────────────────────────────────────────

    def _register(self, p: CapabilityProvider, persist: bool = True) -> None:
        with self._lock:
            # Deduplicate by name + capability
            key = f"{p.name.lower()}::{p.capability.value}"
            existing_id = self._by_name.get(key)
            if existing_id and existing_id in self._providers:
                old = self._providers[existing_id]
                # Update fields, keep provider_id and usage stats
                old.available = p.available
                old.executable = p.executable or old.executable
                old.version = p.version or old.version
                old.path = p.path or old.path
                old.interface = p.interface or old.interface
                old.health = p.health
                old.last_checked = p.last_checked
                old.metadata.update(p.metadata)
                if persist:
                    self._persist(old)
                return

            self._providers[p.provider_id] = p
            self._by_name[key] = p.provider_id
            if p.capability not in self._by_capability:
                self._by_capability[p.capability] = []
            if p.provider_id not in self._by_capability[p.capability]:
                self._by_capability[p.capability].append(p.provider_id)
            if persist:
                self._persist(p)

    def register(self, p: CapabilityProvider) -> None:
        self._register(p, persist=True)

    def register_many(self, providers: list[CapabilityProvider]) -> None:
        for p in providers:
            self._register(p, persist=True)

    # ── Query ────────────────────────────────────────────────────────────

    def get_capability(self, cap: CapabilityType | str) -> Capability:
        if isinstance(cap, str):
            cap = CapabilityType(cap)
        with self._lock:
            ids = self._by_capability.get(cap, [])
            providers = [self._providers[i] for i in ids if i in self._providers]
            return Capability(capability=cap, providers=providers)

    def get_provider(self, name: str, capability: Optional[CapabilityType] = None) -> Optional[CapabilityProvider]:
        with self._lock:
            if capability:
                key = f"{name.lower()}::{capability.value}"
                pid = self._by_name.get(key)
                return self._providers.get(pid) if pid else None
            # Search any capability
            for key, pid in self._by_name.items():
                if key.startswith(name.lower() + "::"):
                    return self._providers.get(pid)
            return None

    def best(self, capability: CapabilityType | str) -> Optional[CapabilityProvider]:
        return self.get_capability(capability).best_provider()

    def all_providers(self) -> list[CapabilityProvider]:
        with self._lock:
            return list(self._providers.values())

    def available_capabilities(self) -> list[CapabilityType]:
        with self._lock:
            result = []
            for cap, ids in self._by_capability.items():
                if any(self._providers[i].available for i in ids if i in self._providers):
                    result.append(cap)
            return result

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "last_scan": self._last_scan,
                "provider_count": len(self._providers),
                "capabilities": {
                    cap.value: self.get_capability(cap).to_dict()
                    for cap in self._by_capability
                },
            }

    def mark_scan_complete(self) -> None:
        self._last_scan = time.time()

    def record_usage(self, provider_id: str, success: bool, latency_ms: Optional[float] = None) -> None:
        with self._lock:
            p = self._providers.get(provider_id)
            if p:
                p.mark_used(success=success, latency_ms=latency_ms)
                self._persist(p)
