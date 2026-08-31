"""Baseline classifier training — sklearn optional path with pure fallback."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class TrainedModel:
    model_id: str
    model_version: str
    backend: str
    feature_names: tuple[str, ...]
    features_version: str
    dataset_hash: str
    artifact: Any
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def predict_proba_positive(self, X: np.ndarray) -> np.ndarray:
        art = self.artifact
        if self.backend == "sklearn":
            return art.predict_proba(X)[:, 1]
        # pure threshold on first feature
        w = art.get("weights")
        b = art.get("bias", 0.0)
        z = X @ w + b
        return 1.0 / (1.0 + np.exp(-z))


def _dataset_hash(X: np.ndarray, y: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(X.tobytes())
    h.update(y.tobytes())
    return h.hexdigest()[:16]


def train_baseline_classifier(
    X: np.ndarray,
    y: np.ndarray,
    *,
    feature_names: tuple[str, ...],
    features_version: str = "feat-v1",
    model_id: str = "baseline_rf",
    model_version: str = "1",
    random_state: int = 42,
) -> TrainedModel:
    if len(X) == 0 or len(y) == 0:
        raise ValueError("empty training set")
    ds = _dataset_hash(X, y)
    try:
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.calibration import CalibratedClassifierCV

        base = RandomForestClassifier(
            n_estimators=50,
            max_depth=4,
            random_state=random_state,
            n_jobs=1,
        )
        # small data: fit base then optional calibration
        if len(X) >= 30:
            clf = CalibratedClassifierCV(base, method="sigmoid", cv=3)
        else:
            clf = base
        clf.fit(X, y)
        proba = clf.predict_proba(X)[:, 1] if hasattr(clf, "predict_proba") else clf.predict(X)
        acc = float(np.mean((proba >= 0.5).astype(int) == y))
        return TrainedModel(
            model_id=model_id,
            model_version=model_version,
            backend="sklearn",
            feature_names=feature_names,
            features_version=features_version,
            dataset_hash=ds,
            artifact=clf,
            metrics={"train_acc": acc},
            metadata={"n_samples": int(len(y)), "random_state": random_state},
        )
    except Exception:
        # logistic-like pure numpy fallback
        yf = y.astype(float)
        w = np.linalg.lstsq(X, yf, rcond=None)[0]
        bias = float(np.mean(yf - X @ w))
        art = {"weights": w, "bias": bias}
        z = 1.0 / (1.0 + np.exp(-(X @ w + bias)))
        acc = float(np.mean((z >= 0.5).astype(int) == y))
        return TrainedModel(
            model_id=model_id,
            model_version=model_version,
            backend="numpy_logit",
            feature_names=feature_names,
            features_version=features_version,
            dataset_hash=ds,
            artifact=art,
            metrics={"train_acc": acc},
            metadata={"n_samples": int(len(y)), "fallback": True},
        )
