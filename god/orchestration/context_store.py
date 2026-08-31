"""CognitiveContext store — MemoryStore JSON, no schema migration."""

from __future__ import annotations

import json
from threading import Lock
from typing import Any, Optional

from .models.context import (
    CognitiveContext,
    ContextStatus,
    assert_status_transition,
)
from god.memory.database import utc_now


class ContextStore:
    PREFIX = "orch_context_v1:"

    def __init__(self, memory_store: Any = None) -> None:
        self._memory = memory_store
        self._local: dict[str, CognitiveContext] = {}
        self._locks: dict[str, Lock] = {}
        self._global = Lock()

    def _lock_for(self, context_id: str) -> Lock:
        with self._global:
            if context_id not in self._locks:
                self._locks[context_id] = Lock()
            return self._locks[context_id]

    def save(self, ctx: CognitiveContext) -> CognitiveContext:
        with self._lock_for(ctx.context_id):
            ctx.updated_at = utc_now()
            self._local[ctx.context_id] = ctx
            if self._memory is not None:
                try:
                    self._memory.set_state(
                        self.PREFIX + ctx.context_id, json.dumps(ctx.to_dict())
                    )
                except Exception:
                    pass
            return ctx

    def get(self, context_id: str) -> Optional[CognitiveContext]:
        if context_id in self._local:
            return self._local[context_id]
        if self._memory is None:
            return None
        try:
            raw = self._memory.get_state(self.PREFIX + context_id)
            if not raw:
                return None
            d = json.loads(raw) if isinstance(raw, str) else raw
            ctx = CognitiveContext.from_dict(d)
            self._local[context_id] = ctx
            return ctx
        except Exception:
            return None

    def transition_status(
        self, context_id: str, to_status: ContextStatus
    ) -> CognitiveContext:
        with self._lock_for(context_id):
            ctx = self.get(context_id)
            if ctx is None:
                raise KeyError(f"context not found: {context_id}")
            assert_status_transition(ctx.status, to_status)
            ctx.status = to_status
            ctx.updated_at = utc_now()
            self._local[context_id] = ctx
            if self._memory is not None:
                try:
                    self._memory.set_state(
                        self.PREFIX + context_id, json.dumps(ctx.to_dict())
                    )
                except Exception:
                    pass
            return ctx
