"""Multi-strategy registry — all candidates retained (anti-survivorship).

Historical versions immutable. No single "best_strategy" overwrite.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from god.memory.database import utc_now

from .models import LifecycleState, ResearchStrategy, TransitionRecord


class StrategyRegistry:
    """In-memory multi-strategy store with optional MemoryStore persistence key."""

    def __init__(self, memory_store: Any = None) -> None:
        # key: (strategy_id, version) → ResearchStrategy
        self._versions: dict[tuple[str, int], ResearchStrategy] = {}
        # strategy_id → sorted list of version numbers
        self._lineage: dict[str, list[int]] = {}
        self._transitions: list[TransitionRecord] = []
        self._memory = memory_store
        self._persist_key = "research_strategy_registry_v1"

    def register(self, strategy: ResearchStrategy) -> ResearchStrategy:
        key = (strategy.strategy_id, strategy.version)
        if key in self._versions:
            # immutable historical versions — reject overwrite
            existing = self._versions[key]
            if existing.content_hash and strategy.content_hash:
                if existing.content_hash != strategy.content_hash:
                    raise ValueError(
                        f"immutable version conflict: {strategy.identity_key()}"
                    )
            return existing

        self._versions[key] = strategy
        versions = self._lineage.setdefault(strategy.strategy_id, [])
        if strategy.version not in versions:
            versions.append(strategy.version)
            versions.sort()
        self._maybe_persist()
        return strategy

    def get(
        self, strategy_id: str, version: Optional[int] = None
    ) -> Optional[ResearchStrategy]:
        if version is not None:
            return self._versions.get((strategy_id, version))
        # latest
        vers = self._lineage.get(strategy_id)
        if not vers:
            return None
        return self._versions.get((strategy_id, vers[-1]))

    def get_version(
        self, strategy_id: str, version: int
    ) -> Optional[ResearchStrategy]:
        return self._versions.get((strategy_id, version))

    def list_all(self) -> list[ResearchStrategy]:
        return list(self._versions.values())

    def list_by_state(self, state: LifecycleState) -> list[ResearchStrategy]:
        return [s for s in self._versions.values() if s.lifecycle_state == state]

    def list_versions(self, strategy_id: str) -> list[ResearchStrategy]:
        vers = self._lineage.get(strategy_id, [])
        return [self._versions[(strategy_id, v)] for v in vers if (strategy_id, v) in self._versions]

    def list_failed_or_retired(self) -> list[ResearchStrategy]:
        terminal = {LifecycleState.RETIRED, LifecycleState.REJECTED, LifecycleState.DEGRADED}
        return [s for s in self._versions.values() if s.lifecycle_state in terminal]

    def children_of(self, parent_id: str, parent_version: Optional[int] = None) -> list[ResearchStrategy]:
        out = []
        for s in self._versions.values():
            if s.parent_strategy_id == parent_id:
                if parent_version is None or s.parent_version == parent_version:
                    out.append(s)
        return out

    def genealogy(self, strategy_id: str) -> list[ResearchStrategy]:
        """Walk parent chain (oldest first)."""
        chain: list[ResearchStrategy] = []
        current = self.get(strategy_id)
        seen: set[str] = set()
        while current is not None:
            key = current.identity_key()
            if key in seen:
                break
            seen.add(key)
            chain.append(current)
            if current.parent_strategy_id is None:
                break
            current = self.get(
                current.parent_strategy_id, current.parent_version
            )
        chain.reverse()
        return chain

    def record_transition(self, record: TransitionRecord) -> None:
        self._transitions.append(record)

    def transitions_for(self, strategy_id: str) -> list[TransitionRecord]:
        return [t for t in self._transitions if t.strategy_id == strategy_id]

    def update(self, strategy: ResearchStrategy) -> ResearchStrategy:
        """Update mutable fields of the *current* registered version (state, meta).

        Does not allow changing parameters / content_hash of historical version.
        """
        key = (strategy.strategy_id, strategy.version)
        if key not in self._versions:
            return self.register(strategy)
        existing = self._versions[key]
        # protect immutable core
        if existing.content_hash and strategy.content_hash != existing.content_hash:
            # allow only lifecycle / observation / retirement fields to change
            strategy.parameters = dict(existing.parameters)
            strategy.content_hash = existing.content_hash
        strategy.updated_at = utc_now()
        self._versions[key] = strategy
        self._maybe_persist()
        return strategy

    def _maybe_persist(self) -> None:
        if self._memory is None:
            return
        try:
            payload = {
                "versions": [s.to_dict() for s in self._versions.values()],
                "lineage": {k: list(v) for k, v in self._lineage.items()},
            }
            self._memory.set_state(self._persist_key, json.dumps(payload, default=str))
        except Exception:
            pass  # persistence best-effort; registry remains authoritative in-process

    def load_from_memory(self) -> int:
        if self._memory is None:
            return 0
        try:
            raw = self._memory.get_state(self._persist_key)
            if not raw:
                return 0
            data = json.loads(raw) if isinstance(raw, str) else raw
            count = 0
            for d in data.get("versions", []):
                s = ResearchStrategy.from_dict(d)
                key = (s.strategy_id, s.version)
                self._versions[key] = s
                vers = self._lineage.setdefault(s.strategy_id, [])
                if s.version not in vers:
                    vers.append(s.version)
                    vers.sort()
                count += 1
            return count
        except Exception:
            return 0
