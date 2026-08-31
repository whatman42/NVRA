"""Experiment registry — including failed experiments (learning from failure)."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.memory.models import Experiment, ExperimentResult
from god.memory.repositories import MemoryStore

from .models import ExperimentOutcome, ExperimentStatus


class ExperimentRegistry:
    """Persist experiments via MemoryStore; track outcomes in-process index."""

    def __init__(self, store: MemoryStore) -> None:
        self.store = store
        self._index: dict[str, Experiment] = {}
        self._results: dict[str, list[ExperimentResult]] = {}
        self._failed_ids: set[str] = set()

    def register(
        self,
        name: str,
        *,
        hypothesis_id: Optional[str] = None,
        config: Optional[dict] = None,
        priority: float = 0.0,
    ) -> Experiment:
        exp = Experiment.create(
            name=name,
            hypothesis_id=hypothesis_id,
            config=config or {},
            priority=priority,
            status=ExperimentStatus.PENDING.value,
        )
        self.store.upsert_experiment(exp)
        self._index[exp.experiment_id] = exp
        return exp

    def start(self, experiment_id: str) -> Experiment:
        exp = self._require(experiment_id)
        exp.status = ExperimentStatus.RUNNING.value
        exp.started_at = utc_now()
        exp.updated_at = exp.started_at
        self.store.upsert_experiment(exp)
        return exp

    def complete(
        self,
        experiment_id: str,
        *,
        outcome: ExperimentOutcome,
        metrics: Optional[dict] = None,
        notes: Optional[str] = None,
    ) -> ExperimentResult:
        exp = self._require(experiment_id)
        passed = outcome == ExperimentOutcome.PASS
        if outcome in (ExperimentOutcome.FAIL, ExperimentOutcome.ERROR):
            exp.status = ExperimentStatus.FAILED.value
            self._failed_ids.add(experiment_id)
        elif outcome == ExperimentOutcome.INCONCLUSIVE:
            exp.status = ExperimentStatus.COMPLETED.value
        else:
            exp.status = ExperimentStatus.COMPLETED.value
        exp.finished_at = utc_now()
        exp.updated_at = exp.finished_at
        self.store.upsert_experiment(exp)

        result = ExperimentResult.create(
            experiment_id,
            metrics=metrics or {},
            passed=passed if outcome != ExperimentOutcome.INCONCLUSIVE else None,
            notes=notes or outcome.value,
        )
        self.store.add_experiment_result(result)
        self._results.setdefault(experiment_id, []).append(result)
        return result

    def list_failed(self) -> list[Experiment]:
        return [self._index[i] for i in self._failed_ids if i in self._index]

    def get(self, experiment_id: str) -> Optional[Experiment]:
        return self._index.get(experiment_id)

    def results_for(self, experiment_id: str) -> list[ExperimentResult]:
        return list(self._results.get(experiment_id, []))

    def _require(self, experiment_id: str) -> Experiment:
        if experiment_id not in self._index:
            # reconstruct minimal shell if only DB was used — still require in-index for registry ops
            raise KeyError(f"experiment not in registry: {experiment_id}")
        return self._index[experiment_id]
