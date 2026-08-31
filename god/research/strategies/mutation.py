"""Generic, seeded, reproducible mutation framework.

Produces a *new* candidate version. Never auto-promotes.
Does not hardcode indicators as strategy law.
"""

from __future__ import annotations

import copy
import hashlib
from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash

from .models import LifecycleState, MutationRecord, MutationType, ResearchStrategy


class MutationEngine:
    """Bounded, auditable mutations → new ResearchStrategy candidate."""

    def mutate(
        self,
        parent: ResearchStrategy,
        *,
        mutation_type: MutationType = MutationType.PARAMETER_MUTATION,
        changes: Optional[dict[str, Any]] = None,
        seed: Optional[int] = None,
        name_suffix: Optional[str] = None,
        actor: str = "mutation",
    ) -> tuple[ResearchStrategy, MutationRecord]:
        """Create child candidate from parent. Historical parent remains immutable."""
        if parent.lifecycle_state == LifecycleState.RETIRED:
            # still allowed to spawn research offspring from retired knowledge
            pass

        changes = dict(changes or {})
        if seed is not None and not changes:
            # deterministic synthetic parameter nudge for reproducibility tests
            changes = self._seeded_parameter_delta(parent.parameters, seed)

        new_params = copy.deepcopy(parent.parameters)
        for k, v in changes.items():
            new_params[k] = v

        child_version = parent.version + 1
        # new identity for mutated line (same logical family can share prefix in name)
        child_id = str(uuid4())
        name = parent.name
        if name_suffix:
            name = f"{parent.name}{name_suffix}"
        elif seed is not None:
            name = f"{parent.name}_m{seed}"

        child = ResearchStrategy.create(
            name=name,
            parameters=new_params,
            hypothesis_ref=parent.hypothesis_ref,
            experiment_refs=list(parent.experiment_refs),
            dataset_refs=list(parent.dataset_refs),
            assumptions=list(parent.assumptions),
            methodology=parent.methodology,
            parent_strategy_id=parent.strategy_id,
            parent_version=parent.version,
            version=child_version,
            lifecycle_state=LifecycleState.CANDIDATE,
            actor=actor,
            strategy_id=child_id,
            metadata={
                "mutated_from": parent.identity_key(),
                "mutation_type": mutation_type.value,
            },
        )

        mut_id = str(uuid4())
        prov = build_provenance(
            origin="mutation",
            payload={
                "parent": parent.identity_key(),
                "child": child.identity_key(),
                "changes": changes,
                "seed": seed,
            },
        )
        record = MutationRecord(
            mutation_id=mut_id,
            parent_strategy_id=parent.strategy_id,
            parent_version=parent.version,
            child_strategy_id=child.strategy_id,
            child_version=child.version,
            mutation_type=mutation_type,
            changes=changes,
            seed=seed,
            timestamp=utc_now(),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
        )
        child.mutation_history = list(parent.mutation_history) + [mut_id]
        return child, record

    def _seeded_parameter_delta(
        self, params: dict[str, Any], seed: int
    ) -> dict[str, Any]:
        """Deterministic, bounded numeric nudge when seed given and no explicit changes."""
        h = hashlib.sha256(f"mut:{seed}:{sorted(params.items())}".encode()).hexdigest()
        delta_bucket = int(h[:8], 16) % 21 - 10  # -10 .. +10
        out: dict[str, Any] = {}
        for k, v in params.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                # relative 1% * bucket, bounded
                out[k] = type(v)(v * (1.0 + delta_bucket * 0.01))
            else:
                out[k] = v
        if not out and params:
            # at least mark seed
            out = dict(params)
            out["_seed_marker"] = seed
        elif not params:
            out = {"_seed_marker": seed}
        return out
