"""Feature importance monitoring — permutation-based (no mandatory SHAP).

SHAP is optional and only attempted on HIGH_PERFORMANCE profiles.
Pruning requires repeated evidence and never removes safety-critical features.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np

from .train import TrainedModel

# Features that must never be pruned (safety / structural)
PROTECTED_FEATURES = frozenset(
    {
        "ret_1",
        "ret_5",
        "vol_10",
        "close",
        "spread",
        "session",
    }
)


@dataclass
class FeatureImportanceReport:
    importances: dict[str, float] = field(default_factory=dict)
    method: str = "permutation"
    pruned: list[str] = field(default_factory=list)
    protected_kept: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "importances": dict(self.importances),
            "method": self.method,
            "pruned": list(self.pruned),
            "protected_kept": list(self.protected_kept),
            "notes": list(self.notes),
        }


def permutation_importance(
    model: TrainedModel,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: Sequence[str],
    *,
    n_repeats: int = 3,
    random_state: int = 42,
) -> dict[str, float]:
    """Mean accuracy drop when each feature is shuffled (OOS-safe if X is OOS)."""
    if len(X) < 5 or len(feature_names) == 0:
        return {n: 0.0 for n in feature_names}
    rng = np.random.default_rng(random_state)
    base_p = model.predict_proba_positive(X)
    base_acc = float(np.mean((base_p >= 0.5).astype(int) == y))
    scores: dict[str, float] = {}
    n_feat = min(X.shape[1], len(feature_names))
    for j in range(n_feat):
        drops = []
        for _ in range(n_repeats):
            Xp = X.copy()
            Xp[:, j] = rng.permutation(Xp[:, j])
            p = model.predict_proba_positive(Xp)
            acc = float(np.mean((p >= 0.5).astype(int) == y))
            drops.append(base_acc - acc)
        scores[str(feature_names[j])] = float(np.mean(drops))
    return scores


def try_shap_importance(
    model: TrainedModel,
    X: np.ndarray,
    feature_names: Sequence[str],
) -> Optional[dict[str, float]]:
    """Optional SHAP — returns None if shap/torch unavailable. Never required."""
    try:
        import shap  # type: ignore
    except Exception:
        return None
    if model.backend != "sklearn":
        return None
    try:
        explainer = shap.Explainer(model.artifact.predict_proba, X[: min(50, len(X))])
        sv = explainer(X[: min(50, len(X))])
        vals = np.abs(sv.values[:, :, 1]).mean(axis=0) if sv.values.ndim == 3 else np.abs(sv.values).mean(axis=0)
        return {str(feature_names[i]): float(vals[i]) for i in range(min(len(feature_names), len(vals)))}
    except Exception:
        return None


def evaluate_features(
    model: TrainedModel,
    X: np.ndarray,
    y: np.ndarray,
    feature_names: Sequence[str],
    *,
    allow_shap: bool = False,
    prune_threshold: float = 0.0,
    require_repeats: int = 2,
    prior_low_importance: Optional[Sequence[str]] = None,
) -> FeatureImportanceReport:
    """Compute importance; prune only features that repeatedly score below threshold."""
    notes: list[str] = []
    method = "permutation"
    imps = permutation_importance(model, X, y, feature_names)
    if allow_shap:
        shap_imps = try_shap_importance(model, X, feature_names)
        if shap_imps:
            # Blend lightly
            for k, v in shap_imps.items():
                imps[k] = 0.5 * imps.get(k, 0.0) + 0.5 * v
            method = "permutation+shap"
            notes.append("shap_blended")
        else:
            notes.append("shap_unavailable")

    prior = set(prior_low_importance or [])
    pruned: list[str] = []
    protected: list[str] = []
    for name, score in imps.items():
        if name in PROTECTED_FEATURES:
            protected.append(name)
            continue
        if score <= prune_threshold and name in prior:
            # Repeated evidence
            pruned.append(name)
        elif score <= prune_threshold:
            notes.append(f"candidate_low:{name}")

    return FeatureImportanceReport(
        importances=imps,
        method=method,
        pruned=pruned,
        protected_kept=protected,
        notes=notes,
    )
