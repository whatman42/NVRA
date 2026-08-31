"""Strategy comparison — produces evidence, never automatic live winner.

Supports baseline (naive / passive / previous version / null).
Metrics are generic observations, not universal promotion laws.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import build_provenance

from .models import ComparisonEvidence, ResearchStrategy


class ComparisonEngine:
    def compare(
        self,
        strategy_a: ResearchStrategy,
        strategy_b: ResearchStrategy,
        *,
        baseline: Optional[ResearchStrategy] = None,
        observations: Optional[dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> ComparisonEvidence:
        """Record comparison evidence. Does not promote or execute."""
        obs = dict(observations or {})
        # Merge known performance_observations if present (descriptive only)
        if strategy_a.performance_observations:
            obs.setdefault("a_performance", dict(strategy_a.performance_observations))
        if strategy_b.performance_observations:
            obs.setdefault("b_performance", dict(strategy_b.performance_observations))
        if baseline and baseline.performance_observations:
            obs.setdefault("baseline_performance", dict(baseline.performance_observations))

        obs.setdefault(
            "sample_characteristics",
            {
                "a_experiments": list(strategy_a.experiment_refs),
                "b_experiments": list(strategy_b.experiment_refs),
                "a_state": strategy_a.lifecycle_state.value,
                "b_state": strategy_b.lifecycle_state.value,
            },
        )
        obs.setdefault(
            "failure_history",
            {
                "a_retired": strategy_a.retirement_reason,
                "b_retired": strategy_b.retirement_reason,
            },
        )

        prov = build_provenance(
            origin="strategy_comparison",
            payload={
                "a": strategy_a.identity_key(),
                "b": strategy_b.identity_key(),
                "baseline": baseline.identity_key() if baseline else None,
            },
        )
        return ComparisonEvidence(
            comparison_id=str(uuid4()),
            strategy_a_id=strategy_a.strategy_id,
            strategy_a_version=strategy_a.version,
            strategy_b_id=strategy_b.strategy_id,
            strategy_b_version=strategy_b.version,
            baseline_id=baseline.strategy_id if baseline else None,
            observations=obs,
            notes=notes,
            timestamp=utc_now(),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
            },
        )

    def compare_to_baseline(
        self,
        strategy: ResearchStrategy,
        baseline: ResearchStrategy,
        *,
        observations: Optional[dict[str, Any]] = None,
        notes: Optional[str] = None,
    ) -> ComparisonEvidence:
        return self.compare(
            strategy,
            baseline,
            baseline=baseline,
            observations=observations,
            notes=notes or "baseline_comparison",
        )
