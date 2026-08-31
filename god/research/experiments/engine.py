"""Experiment engine — additive over 4A ExperimentRegistry."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from god.research.engine import ResearchEngine
from god.research.models import ExperimentOutcome
from god.research.registry import ExperimentRegistry

from .metadata import ExperimentMetadata, ExperimentOutcomeExt


class ExperimentEngine:
    """Record rich metadata while persisting via frozen Memory paths."""

    def __init__(self, research: ResearchEngine) -> None:
        self.research = research
        self.registry: ExperimentRegistry = research.registry
        self._meta: dict[str, ExperimentMetadata] = {}
        self._families: dict[str, list[str]] = {}

    def design(
        self,
        name: str,
        *,
        hypothesis_id: Optional[str] = None,
        dataset_ref: Optional[str] = None,
        parameters: Optional[dict] = None,
        assumptions: Optional[list[str]] = None,
        random_seed: Optional[int] = None,
        methodology: Optional[str] = None,
        family_id: Optional[str] = None,
        provenance: Optional[dict] = None,
    ) -> ExperimentMetadata:
        exp = self.research.design_experiment(
            name,
            hypothesis_id=hypothesis_id,
            config={
                "dataset_ref": dataset_ref,
                "parameters": parameters or {},
                "assumptions": assumptions or [],
                "random_seed": random_seed,
                "methodology": methodology,
                "family_id": family_id,
            },
        )
        fid = family_id or str(uuid4())
        family = self._families.setdefault(fid, [])
        family.append(exp.experiment_id)
        meta = ExperimentMetadata(
            experiment_id=exp.experiment_id,
            hypothesis_id=hypothesis_id,
            dataset_ref=dataset_ref,
            parameters=dict(parameters or {}),
            assumptions=list(assumptions or []),
            random_seed=random_seed,
            methodology=methodology,
            provenance=dict(provenance or {}),
            family_id=fid,
            family_size=len(family),
            rank_in_family=len(family),
            selection_bias_note=(
                f"Member of family {fid} size={len(family)}; "
                "best-of-family is not evidence of true edge without further controls"
            ),
        )
        # Update family_size on all members
        for eid in family:
            if eid in self._meta:
                self._meta[eid].family_size = len(family)
        self._meta[exp.experiment_id] = meta
        return meta

    def complete(
        self,
        experiment_id: str,
        outcome: ExperimentOutcomeExt | str,
        *,
        result: Optional[dict] = None,
        failure_reason: Optional[str] = None,
        validation_flags: Optional[dict[str, bool]] = None,
    ) -> ExperimentMetadata:
        oc = (
            outcome
            if isinstance(outcome, ExperimentOutcomeExt)
            else ExperimentOutcomeExt(outcome)
        )
        # Map to 4A registry outcomes
        if oc in (ExperimentOutcomeExt.PASS,):
            base = ExperimentOutcome.PASS
        elif oc in (
            ExperimentOutcomeExt.FAIL,
            ExperimentOutcomeExt.REJECTED,
            ExperimentOutcomeExt.TIMEOUT,
            ExperimentOutcomeExt.INVALID,
            ExperimentOutcomeExt.OVERFIT_FLAG,
            ExperimentOutcomeExt.ERROR,
        ):
            base = ExperimentOutcome.FAIL
        else:
            base = ExperimentOutcome.INCONCLUSIVE

        self.research.run_experiment_record(
            experiment_id,
            outcome=base,
            metrics=result or {},
            notes=failure_reason or oc.value,
        )
        meta = self._meta.get(experiment_id)
        if meta is None:
            meta = ExperimentMetadata(experiment_id=experiment_id)
            self._meta[experiment_id] = meta
        meta.outcome = oc.value
        meta.result = result
        meta.failure_reason = failure_reason
        if validation_flags:
            meta.validation_flags.update(validation_flags)
        # Refresh family_size
        if meta.family_id and meta.family_id in self._families:
            meta.family_size = len(self._families[meta.family_id])
        return meta

    def get_metadata(self, experiment_id: str) -> Optional[ExperimentMetadata]:
        return self._meta.get(experiment_id)

    def list_failed_metadata(self) -> list[ExperimentMetadata]:
        failed_ids = {e.experiment_id for e in self.registry.list_failed()}
        return [m for eid, m in self._meta.items() if eid in failed_ids]

    def family_members(self, family_id: str) -> list[ExperimentMetadata]:
        ids = self._families.get(family_id, [])
        return [self._meta[i] for i in ids if i in self._meta]
