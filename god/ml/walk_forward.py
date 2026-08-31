"""Walk-forward engine — OOS folds; no random split."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .features import FeatureSchema, build_feature_matrix, next_direction_labels
from .split import TimeSeriesSplitSpec, time_series_splits
from .train import TrainedModel, train_baseline_classifier


@dataclass
class FoldResult:
    fold: int
    train_size: int
    test_size: int
    accuracy: float
    n_pred: int


@dataclass
class WalkForwardResult:
    folds: list[FoldResult] = field(default_factory=list)
    mean_oos_accuracy: float = 0.0
    last_model: Optional[TrainedModel] = None
    features_version: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "folds": [
                {
                    "fold": f.fold,
                    "train_size": f.train_size,
                    "test_size": f.test_size,
                    "accuracy": f.accuracy,
                    "n_pred": f.n_pred,
                }
                for f in self.folds
            ],
            "mean_oos_accuracy": self.mean_oos_accuracy,
            "features_version": self.features_version,
            "notes": list(self.notes),
            "promoted_to_live": False,  # never auto
        }


class WalkForwardEngine:
    def __init__(self, split_spec: Optional[TimeSeriesSplitSpec] = None) -> None:
        self.split_spec = split_spec or TimeSeriesSplitSpec()

    def run(self, closes: list[float] | np.ndarray) -> WalkForwardResult:
        X, idxs, schema = build_feature_matrix(closes)
        y, y_idxs = next_direction_labels(closes, idxs)
        # align X rows to labeled indices
        idx_map = {int(t): i for i, t in enumerate(idxs)}
        rows = []
        labels = []
        for t, lab in zip(y_idxs, y):
            if int(t) in idx_map:
                rows.append(X[idx_map[int(t)]])
                labels.append(lab)
        if not rows:
            return WalkForwardResult(notes=["insufficient_data"])
        Xa = np.asarray(rows)
        ya = np.asarray(labels)
        folds: list[FoldResult] = []
        last: Optional[TrainedModel] = None
        for i, (tr, te) in enumerate(time_series_splits(len(Xa), self.split_spec)):
            model = train_baseline_classifier(
                Xa[tr],
                ya[tr],
                feature_names=schema.names,
                features_version=schema.version,
                model_version=str(i + 1),
            )
            proba = model.predict_proba_positive(Xa[te])
            pred = (proba >= 0.5).astype(int)
            acc = float(np.mean(pred == ya[te])) if len(te) else 0.0
            folds.append(
                FoldResult(
                    fold=i,
                    train_size=len(tr),
                    test_size=len(te),
                    accuracy=acc,
                    n_pred=len(te),
                )
            )
            last = model
        mean_acc = float(np.mean([f.accuracy for f in folds])) if folds else 0.0
        return WalkForwardResult(
            folds=folds,
            mean_oos_accuracy=mean_acc,
            last_model=last,
            features_version=schema.version,
            notes=["walk_forward_complete"] if folds else ["no_folds"],
        )
