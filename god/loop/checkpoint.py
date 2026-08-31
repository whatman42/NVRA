"""Workflow checkpoint for discovery→selection→fusion→attention. No schema migration."""

from __future__ import annotations

import json
from typing import Any, Optional

from god.research.provenance import content_hash
from god.memory.database import utc_now


class CycleCheckpointStore:
    PREFIX = "orch_cycle_v1:"

    def __init__(self, memory_store: Any = None) -> None:
        self._memory = memory_store
        self._local: dict[str, dict[str, Any]] = {}

    def save(
        self,
        cycle_id: str,
        stage: str,
        payload: dict[str, Any],
    ) -> str:
        body = {
            "cycle_id": cycle_id,
            "stage": stage,
            "payload": payload,
        }
        ch = content_hash(body)
        body["content_hash"] = ch
        body["timestamp"] = utc_now()
        cp_id = "cycp-" + ch[:20]
        self._local[cp_id] = body
        self._local[f"latest:{cycle_id}"] = body
        if self._memory is not None:
            try:
                self._memory.set_state(self.PREFIX + cp_id, json.dumps(body))
                self._memory.set_state(self.PREFIX + f"latest:{cycle_id}", cp_id)
            except Exception:
                pass
        return cp_id

    def latest(self, cycle_id: str) -> Optional[dict[str, Any]]:
        key = f"latest:{cycle_id}"
        if key in self._local:
            return self._local[key]
        if self._memory is None:
            return None
        try:
            lid = self._memory.get_state(self.PREFIX + key)
            if not lid:
                return None
            raw = self._memory.get_state(self.PREFIX + str(lid))
            if not raw:
                return None
            d = json.loads(raw) if isinstance(raw, str) else raw
            # verify hash
            body = {
                "cycle_id": d["cycle_id"],
                "stage": d["stage"],
                "payload": d["payload"],
            }
            if content_hash(body) != d.get("content_hash"):
                return {"status": "CORRUPTED", "reason": "hash_mismatch"}
            return d
        except Exception:
            return None
