"""Constrained ensemble abstraction for tree-model families.

On CONSERVATIVE: sequential only, small/no parallel training, memory-light.
Does not auto-promote champions — validation pipeline remains authoritative.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np

from .hardware import ResourceGovernor, ResourceLimits
from .model_capabilities import ModelCapabilityRegistry, allowed_families_for_limits
from .train import TrainedModel, train_baseline_classifier


@dataclass
class EnsembleMember:
    family: str
    model: TrainedModel
    weight: float = 1.0


@dataclass
class EnsembleResult:
    members: list[EnsembleMember] = field(default_factory=list)
    combined_backend: str = "weighted_avg"
    metrics: dict[str, float] = field(default_factory=dict)
    sequential: bool = True
    notes: list[str] = field(default_factory=list)

    def predict_proba_positive(self, X: np.ndarray) -> np.ndarray:
        if not self.members:
            return np.full(len(X), 0.5)
        total_w = sum(m.weight for m in self.members) or 1.0
        acc = np.zeros(len(X), dtype=float)
        for m in self.members:
            acc += m.weight * m.model.predict_proba_positive(X)
        return acc / total_w


def train_constrained_ensemble(
    X: np.ndarray,
    y: np.ndarray,
    *,
    feature_names: tuple[str, ...],
    features_version: str = "feat-v1",
    governor: Optional[ResourceGovernor] = None,
    families: Optional[Sequence[str]] = None,
    model_version: str = "1",
) -> EnsembleResult:
    """Train allowed families under resource limits.

    CONSERVATIVE / pressure → sequential single-worker jobs only.
    Caps members by max_ensemble_size.
    """
    gov = governor or ResourceGovernor()
    limits = gov.limits
    caps = ModelCapabilityRegistry(gpu_available=gov.snapshot.gpu_available)
    allowed = list(families) if families else allowed_families_for_limits(limits, caps.all())
    allowed = [
        f
        for f in allowed
        if f not in ("lstm", "gru", "transformer") or limits.allow_heavy_ml
    ]
    # Cap by ensemble size
    max_n = max(1, limits.max_ensemble_size)
    allowed = allowed[:max_n]

    if not limits.allow_ensemble or max_n <= 1:
        preferred = (
            "random_forest"
            if "random_forest" in allowed
            else (allowed[0] if allowed else "numpy_logit")
        )
        if not gov.begin_training():
            return EnsembleResult(notes=["training_blocked_by_pressure"])
        try:
            model = train_baseline_classifier(
                X,
                y,
                feature_names=feature_names,
                features_version=features_version,
                model_id=preferred,
                model_version=model_version,
            )
            return EnsembleResult(
                members=[EnsembleMember(family=preferred, model=model, weight=1.0)],
                sequential=True,
                notes=["ensemble_disabled", f"single={preferred}"],
            )
        finally:
            gov.end_training()

    members: list[EnsembleMember] = []
    notes: list[str] = []
    sequential = limits.sequential_training or limits.max_parallel_train_jobs <= 1

    for fam in allowed:
        if fam in ("lstm", "gru", "transformer"):
            notes.append(f"skip_heavy:{fam}")
            continue
        if not gov.may_start_training():
            notes.append("training_stopped_pressure")
            break
        if not gov.begin_training():
            notes.append("begin_training_denied")
            break
        try:
            model = train_baseline_classifier(
                X,
                y,
                feature_names=feature_names,
                features_version=features_version,
                model_id=fam,
                model_version=model_version,
            )
            members.append(EnsembleMember(family=fam, model=model, weight=1.0))
        except Exception as e:
            notes.append(f"train_fail:{fam}:{type(e).__name__}")
        finally:
            gov.end_training()

    return EnsembleResult(
        members=members,
        sequential=sequential,
        notes=notes or ["ok"],
        metrics={"n_members": float(len(members))},
    )
