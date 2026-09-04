"""Institutional SQLite checkpoint store with production semantic validation.

Opaque workflow payloads remain writable. Lifecycle/recovery claims are fail-closed.
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .checkpoint_schema import (
    CheckpointValidationError,
    ValidationResult,
    is_lifecycle_claim,
    validate_lifecycle_state,
)


class CheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS checkpoints ("
                "run_id TEXT PRIMARY KEY, node TEXT NOT NULL, "
                "state_json TEXT NOT NULL, updated_ns INTEGER NOT NULL)"
            )
            c.commit()

    def save(self, run_id: str, node: str, state: dict[str, Any]) -> None:
        if not isinstance(state, dict):
            raise CheckpointValidationError("state must be a dict")
        if is_lifecycle_claim(node, state):
            result = validate_lifecycle_state(state, node=node)
            if not result.ok or result.classification == "REJECT":
                raise CheckpointValidationError(
                    f"refusing to persist invalid lifecycle checkpoint "
                    f"({result.classification}): {','.join(result.reasons)}"
                )
            if result.classification == "RECONCILIATION_REQUIRED" and (
                state.get("lifecycle") in ("READY", "RUNNING") or node in ("READY", "RUNNING")
            ):
                raise CheckpointValidationError(
                    f"refusing to persist READY/RUNNING without valid reconciliation "
                    f"({result.classification}): {','.join(result.reasons)}"
                )
        payload = json.dumps(state, sort_keys=True, separators=(",", ":"), default=str)
        with sqlite3.connect(self.path) as c:
            c.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET "
                "node=excluded.node, state_json=excluded.state_json, updated_ns=excluded.updated_ns",
                (run_id, node, payload, time.time_ns()),
            )
            c.commit()

    def load(self, run_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.path) as c:
            row = c.execute(
                "SELECT node, state_json, updated_ns FROM checkpoints WHERE run_id=?",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        node, state_json, updated_ns = row[0], row[1], row[2]
        try:
            state = json.loads(state_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(state, dict):
            return None
        if is_lifecycle_claim(node, state):
            result = validate_lifecycle_state(state, node=node)
            if not result.ok or result.classification == "REJECT":
                return None
            return {
                "node": node,
                "state": state,
                "updated_ns": updated_ns,
                "validation": {
                    "classification": result.classification,
                    "reasons": list(result.reasons),
                    "trusted_ready": result.trusted_ready,
                    "trusted_execution": result.trusted_execution,
                },
            }
        return {"node": node, "state": state, "updated_ns": updated_ns}

    def load_trusted_ready(self, run_id: str) -> dict[str, Any] | None:
        """Load only if validation grants trusted_ready (still requires external recon/risk)."""
        loaded = self.load(run_id)
        if loaded is None:
            return None
        meta = loaded.get("validation") or {}
        if meta.get("trusted_ready"):
            return loaded
        return None

    def clear(self, run_id: str) -> None:
        with sqlite3.connect(self.path) as c:
            c.execute("DELETE FROM checkpoints WHERE run_id=?", (run_id,))
            c.commit()


__all__ = [
    "CheckpointStore",
    "CheckpointValidationError",
    "ValidationResult",
    "validate_lifecycle_state",
    "is_lifecycle_claim",
]
