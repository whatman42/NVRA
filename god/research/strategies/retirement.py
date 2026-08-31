"""Strategy retirement — historical knowledge retained, never deleted."""

from __future__ import annotations

from typing import Optional

from .lifecycle import LifecycleEngine
from .models import ResearchStrategy
from .registry import StrategyRegistry


class RetirementService:
    def __init__(
        self,
        registry: StrategyRegistry,
        lifecycle: Optional[LifecycleEngine] = None,
    ) -> None:
        self.registry = registry
        self.lifecycle = lifecycle or LifecycleEngine()

    def retire(
        self,
        strategy: ResearchStrategy,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        replacement_strategy_id: Optional[str] = None,
    ) -> ResearchStrategy:
        s = self.lifecycle.retire(
            strategy,
            reason=reason,
            evidence_refs=evidence_refs,
            replacement_strategy_id=replacement_strategy_id,
            actor="retirement",
        )
        return self.registry.update(s)
