"""Runtime recovery — recompute-safe, fail-closed on corruption."""

from __future__ import annotations

from typing import Any, Optional

from god.loop.checkpoint import CycleCheckpointStore


class RuntimeRecovery:
    def __init__(self, memory_store: Any = None) -> None:
        self._cp = CycleCheckpointStore(memory_store)

    def inspect(self, cycle_id: str) -> dict[str, Any]:
        latest = self._cp.latest(cycle_id)
        if latest is None:
            return {"status": "UNKNOWN", "cycle_id": cycle_id}
        if latest.get("status") == "CORRUPTED":
            return {
                "status": "CORRUPTED",
                "cycle_id": cycle_id,
                "reason": latest.get("reason", "hash_mismatch"),
            }
        return {
            "status": "RESUME",
            "cycle_id": cycle_id,
            "stage": latest.get("stage"),
            "checkpoint": latest,
        }
