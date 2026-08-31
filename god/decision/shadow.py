"""Bounded shadow decision store for N.U.N.G."""

from __future__ import annotations

from typing import Optional

from .models import DecisionConfig, ShadowDecision, ShadowStatus, ValidityState


class ShadowDecisionStore:
    def __init__(self, config: Optional[DecisionConfig] = None) -> None:
        self.config = config or DecisionConfig()
        self._by_id: dict[str, ShadowDecision] = {}
        self._revisions: dict[str, list[ShadowDecision]] = {}  # root_id → revisions
        self._order: list[str] = []

    def put(self, decision: ShadowDecision) -> ShadowDecision:
        root = decision.parent_decision_id or decision.decision_id
        # idempotency: same decision_id
        if decision.decision_id in self._by_id:
            return self._by_id[decision.decision_id]

        revs = self._revisions.setdefault(root, [])
        if len(revs) >= self.config.max_revisions_per_decision:
            # drop oldest revision identity from index only if needed
            oldest = revs.pop(0)
            self._by_id.pop(oldest.decision_id, None)

        revs.append(decision)
        self._by_id[decision.decision_id] = decision
        if decision.decision_id not in self._order:
            self._order.append(decision.decision_id)
        self._trim()
        return decision

    def get(self, decision_id: str) -> Optional[ShadowDecision]:
        return self._by_id.get(decision_id)

    def latest_for_opportunity(self, opportunity_id: str) -> Optional[ShadowDecision]:
        matches = [
            d
            for d in self._by_id.values()
            if d.opportunity_id == opportunity_id
        ]
        if not matches:
            return None
        return max(matches, key=lambda d: d.revision)

    def revisions(self, root_or_id: str) -> list[ShadowDecision]:
        if root_or_id in self._revisions:
            return list(self._revisions[root_or_id])
        d = self._by_id.get(root_or_id)
        if d is None:
            return []
        root = d.parent_decision_id or d.decision_id
        return list(self._revisions.get(root, [d]))

    def recent(self, n: int = 50) -> list[ShadowDecision]:
        ids = self._order[-n:]
        return [self._by_id[i] for i in ids if i in self._by_id]

    def _trim(self) -> None:
        while len(self._order) > self.config.max_decisions:
            old = self._order.pop(0)
            self._by_id.pop(old, None)
