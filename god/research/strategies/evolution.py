"""Evolution engine — controlled path from parent → mutation → candidate → experiment.

Never Candidate → LIVE. Never bypasses lifecycle.
"""

from __future__ import annotations

from typing import Any, Optional

from .lifecycle import LifecycleEngine
from .models import (
    LifecycleState,
    MutationRecord,
    MutationType,
    ResearchStrategy,
)
from .mutation import MutationEngine
from .registry import StrategyRegistry


class EvolutionEngine:
    """Orchestrates mutation + registration + optional experiment linkage."""

    def __init__(
        self,
        registry: StrategyRegistry,
        lifecycle: Optional[LifecycleEngine] = None,
        mutation: Optional[MutationEngine] = None,
    ) -> None:
        self.registry = registry
        self.lifecycle = lifecycle or LifecycleEngine()
        self.mutation = mutation or MutationEngine()
        self._mutation_log: list[MutationRecord] = []

    def propose_candidate_from_hypothesis(
        self,
        name: str,
        *,
        hypothesis_ref: str,
        parameters: Optional[dict] = None,
        experiment_refs: Optional[list[str]] = None,
        dataset_refs: Optional[list[str]] = None,
        assumptions: Optional[list[str]] = None,
        methodology: Optional[str] = None,
    ) -> ResearchStrategy:
        s = ResearchStrategy.create(
            name=name,
            parameters=parameters,
            hypothesis_ref=hypothesis_ref,
            experiment_refs=experiment_refs,
            dataset_refs=dataset_refs,
            assumptions=assumptions,
            methodology=methodology,
            lifecycle_state=LifecycleState.CANDIDATE,
        )
        return self.registry.register(s)

    def evolve(
        self,
        parent: ResearchStrategy,
        *,
        mutation_type: MutationType = MutationType.PARAMETER_MUTATION,
        changes: Optional[dict[str, Any]] = None,
        seed: Optional[int] = None,
        link_experiment_ids: Optional[list[str]] = None,
    ) -> tuple[ResearchStrategy, MutationRecord]:
        """Parent → Mutation Proposal → Candidate (registered, CANDIDATE state)."""
        child, record = self.mutation.mutate(
            parent,
            mutation_type=mutation_type,
            changes=changes,
            seed=seed,
        )
        if link_experiment_ids:
            child.experiment_refs = list(
                dict.fromkeys(child.experiment_refs + list(link_experiment_ids))
            )
        self.registry.register(child)
        self._mutation_log.append(record)
        return child, record

    def advance_to_experimental(
        self,
        strategy: ResearchStrategy,
        *,
        reason: str = "experiment_created",
        evidence_refs: Optional[list[str]] = None,
        experiment_id: Optional[str] = None,
    ) -> ResearchStrategy:
        refs = list(evidence_refs or [])
        if experiment_id:
            refs.append(experiment_id)
            if experiment_id not in strategy.experiment_refs:
                strategy.experiment_refs = list(strategy.experiment_refs) + [experiment_id]
        strategy = self.lifecycle.transition(
            strategy,
            LifecycleState.EXPERIMENTAL,
            reason=reason,
            evidence_refs=refs,
            actor="evolution",
        )
        return self.registry.update(strategy)

    def attach_validation(
        self,
        strategy: ResearchStrategy,
        validation_metadata: dict[str, Any],
        *,
        advance: bool = False,
    ) -> ResearchStrategy:
        strategy.validation_metadata = dict(validation_metadata)
        if advance and strategy.lifecycle_state == LifecycleState.EXPERIMENTAL:
            strategy = self.lifecycle.transition(
                strategy,
                LifecycleState.VALIDATING,
                reason="validation_metadata_attached",
                evidence_refs=list(strategy.experiment_refs),
                actor="evolution",
            )
        return self.registry.update(strategy)

    def mutation_log(self) -> list[MutationRecord]:
        return list(self._mutation_log)
