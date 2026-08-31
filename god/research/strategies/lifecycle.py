"""Lifecycle transitions — explicit reason + evidence_refs + audit trail.

No universal performance law. Transition is driven by caller-supplied evidence.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now

from .models import LifecycleState, ResearchStrategy, TransitionRecord
from .states import assert_transition, can_transition


class LifecycleEngine:
    """Applies validated, audited state transitions to ResearchStrategy."""

    def __init__(self) -> None:
        self._history: list[TransitionRecord] = []

    def transition(
        self,
        strategy: ResearchStrategy,
        to_state: LifecycleState,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        actor: str = "lifecycle",
        metadata: Optional[dict[str, Any]] = None,
    ) -> ResearchStrategy:
        """Apply transition. Idempotent when already in to_state."""
        from_state = strategy.lifecycle_state
        if from_state == to_state:
            # still record no-op for audit if desired — keep light
            return strategy

        assert_transition(from_state, to_state)
        if not reason or not reason.strip():
            raise ValueError("transition requires non-empty reason")

        now = utc_now()
        rec = TransitionRecord(
            transition_id=str(uuid4()),
            strategy_id=strategy.strategy_id,
            version=strategy.version,
            from_state=from_state,
            to_state=to_state,
            reason=reason.strip(),
            evidence_refs=tuple(evidence_refs or ()),
            actor=actor,
            timestamp=now,
            metadata=dict(metadata or {}),
        )
        self._history.append(rec)

        strategy.lifecycle_state = to_state
        strategy.updated_at = now
        # attach last transition id into metadata for traceability
        strategy.metadata = dict(strategy.metadata)
        strategy.metadata["last_transition_id"] = rec.transition_id
        strategy.metadata["last_transition_reason"] = rec.reason
        return strategy

    def degrade(
        self,
        strategy: ResearchStrategy,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        metrics_snapshot: Optional[dict] = None,
        actor: str = "degradation",
    ) -> ResearchStrategy:
        meta = {"metrics_snapshot": metrics_snapshot or {}}
        return self.transition(
            strategy,
            LifecycleState.DEGRADED,
            reason=reason,
            evidence_refs=evidence_refs,
            actor=actor,
            metadata=meta,
        )

    def recover(
        self,
        strategy: ResearchStrategy,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        actor: str = "recovery",
    ) -> ResearchStrategy:
        if strategy.lifecycle_state != LifecycleState.DEGRADED:
            raise ValueError("recovery only from DEGRADED")
        return self.transition(
            strategy,
            LifecycleState.RECOVERY,
            reason=reason,
            evidence_refs=evidence_refs,
            actor=actor,
        )

    def retire(
        self,
        strategy: ResearchStrategy,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        replacement_strategy_id: Optional[str] = None,
        actor: str = "retirement",
    ) -> ResearchStrategy:
        strategy = self.transition(
            strategy,
            LifecycleState.RETIRED,
            reason=reason,
            evidence_refs=evidence_refs,
            actor=actor,
        )
        strategy.retirement_reason = reason
        strategy.retirement_evidence = list(evidence_refs or [])
        strategy.replacement_strategy_id = replacement_strategy_id
        strategy.updated_at = utc_now()
        return strategy

    def history_for(self, strategy_id: str) -> list[TransitionRecord]:
        return [t for t in self._history if t.strategy_id == strategy_id]

    def all_history(self) -> list[TransitionRecord]:
        return list(self._history)

    def is_allowed(self, from_state: LifecycleState, to_state: LifecycleState) -> bool:
        return can_transition(from_state, to_state)
