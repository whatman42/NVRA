"""Capital safety registry — in-process + optional MemoryStore JSON."""

from __future__ import annotations

import json
from typing import Any, Optional

from .models import CapitalStateRecord, CapitalTransitionRecord


class CapitalRegistry:
    PERSIST_KEY = "capital_safety_v1"

    def __init__(self, memory_store: Any = None) -> None:
        self._record: Optional[CapitalStateRecord] = None
        self._transitions: dict[str, CapitalTransitionRecord] = {}
        self._memory = memory_store

    def set_record(self, record: CapitalStateRecord) -> None:
        self._record = record
        self._maybe_persist()

    def get_record(self) -> Optional[CapitalStateRecord]:
        return self._record

    def add_transition(self, tr: CapitalTransitionRecord) -> CapitalTransitionRecord:
        if tr.transition_id in self._transitions:
            return self._transitions[tr.transition_id]  # idempotent
        self._transitions[tr.transition_id] = tr
        self._maybe_persist()
        return tr

    def get_transition(self, transition_id: str) -> Optional[CapitalTransitionRecord]:
        return self._transitions.get(transition_id)

    def list_transitions(self) -> list[CapitalTransitionRecord]:
        return list(self._transitions.values())

    def _maybe_persist(self) -> None:
        if self._memory is None:
            return
        try:
            payload = {
                "record": self._record.to_dict() if self._record else None,
                "transitions": [t.to_dict() for t in self._transitions.values()],
            }
            self._memory.set_state(self.PERSIST_KEY, json.dumps(payload, default=str))
        except Exception:
            pass

    def load_from_memory(self) -> int:
        if self._memory is None:
            return 0
        try:
            raw = self._memory.get_state(self.PERSIST_KEY)
            if not raw:
                return 0
            data = json.loads(raw) if isinstance(raw, str) else raw
            count = 0
            if data.get("record"):
                r = data["record"]
                from .models import CapitalState

                self._record = CapitalStateRecord(
                    record_id=r["record_id"],
                    state=CapitalState(r["state"]),
                    updated_at=r.get("updated_at", ""),
                    last_transition_id=r.get("last_transition_id"),
                    transition_ids=list(r.get("transition_ids") or []),
                    evidence_refs=list(r.get("evidence_refs") or []),
                    provenance=r.get("provenance"),
                    metadata=dict(r.get("metadata") or {}),
                )
                count += 1
            for t in data.get("transitions") or []:
                from .models import CapitalState

                tr = CapitalTransitionRecord(
                    transition_id=t["transition_id"],
                    state_before=CapitalState(t["state_before"]),
                    state_after=CapitalState(t["state_after"]),
                    reason=t["reason"],
                    evidence_refs=tuple(t.get("evidence_refs") or ()),
                    timestamp=t.get("timestamp", ""),
                    actor=t.get("actor", "system"),
                    provenance=t.get("provenance"),
                    metadata=dict(t.get("metadata") or {}),
                )
                self._transitions[tr.transition_id] = tr
                count += 1
            return count
        except Exception:
            return 0
