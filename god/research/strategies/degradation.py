"""Strategy degradation helpers — reason + evidence required.

Degradation does not delete; it records failure for learning.
"""

from __future__ import annotations

from typing import Any, Optional

from .lifecycle import LifecycleEngine
from .models import ResearchStrategy
from .registry import StrategyRegistry


class DegradationService:
    def __init__(
        self,
        registry: StrategyRegistry,
        lifecycle: Optional[LifecycleEngine] = None,
    ) -> None:
        self.registry = registry
        self.lifecycle = lifecycle or LifecycleEngine()

    def degrade(
        self,
        strategy: ResearchStrategy,
        *,
        reason: str,
        evidence_refs: Optional[list[str]] = None,
        metrics_snapshot: Optional[dict[str, Any]] = None,
        detector: str = "manual",
    ) -> ResearchStrategy:
        """Lower status to DEGRADED with full audit trail."""
        allowed_reasons = {
            "performance_degradation",
            "data_quality_issue",
            "execution_assumption_break",
            "validation_failure",
            "regime_mismatch",
            "other",
        }
        # reason is free-form but encouraged to use known tags
        s = self.lifecycle.degrade(
            strategy,
            reason=reason,
            evidence_refs=evidence_refs,
            metrics_snapshot=metrics_snapshot,
            actor=f"degradation:{detector}",
        )
        if metrics_snapshot:
            s.performance_observations = dict(s.performance_observations)
            s.performance_observations["degradation_snapshot"] = metrics_snapshot
        return self.registry.update(s)
