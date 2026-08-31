"""Checkpoint store via MemoryStore.set_state / get_state (no schema migration)."""

from __future__ import annotations

import json
from typing import Any, Optional

from .models.checkpoint import Checkpoint, verify_checkpoint


class CheckpointStore:
    PREFIX = "orch_checkpoint_v1:"

    def __init__(self, memory_store: Any = None) -> None:
        self._memory = memory_store
        self._local: dict[str, Checkpoint] = {}

    def save(self, cp: Checkpoint) -> Checkpoint:
        key = cp.checkpoint_id
        if key in self._local:
            return self._local[key]  # idempotent
        self._local[key] = cp
        if self._memory is not None:
            try:
                self._memory.set_state(self.PREFIX + key, json.dumps(cp.to_dict()))
                # also index latest per context
                self._memory.set_state(
                    self.PREFIX + "latest:" + cp.context_id, cp.checkpoint_id
                )
            except Exception:
                pass
        return cp

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        if checkpoint_id in self._local:
            return self._local[checkpoint_id]
        if self._memory is None:
            return None
        try:
            raw = self._memory.get_state(self.PREFIX + checkpoint_id)
            if not raw:
                return None
            d = json.loads(raw) if isinstance(raw, str) else raw
            cp = Checkpoint.from_dict(d)
            if not verify_checkpoint(cp):
                return None  # treat as missing/corrupt
            self._local[checkpoint_id] = cp
            return cp
        except Exception:
            return None

    def latest_for_context(self, context_id: str) -> Optional[Checkpoint]:
        # scan local first
        candidates = [c for c in self._local.values() if c.context_id == context_id]
        if candidates:
            return max(candidates, key=lambda c: c.timestamp)
        if self._memory is None:
            return None
        try:
            lid = self._memory.get_state(self.PREFIX + "latest:" + context_id)
            if lid:
                return self.get(str(lid))
        except Exception:
            pass
        return None
