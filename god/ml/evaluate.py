"""ML evaluation metrics — not used for broker authorization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass
class EvalReport:
    n: int = 0
    accuracy: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1: float = 0.0
    log_loss: float = 0.0
    brier: float = 0.0
    coverage: float = 1.0
    invalid_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n": self.n,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "log_loss": self.log_loss,
            "brier": self.brier,
            "coverage": self.coverage,
            "invalid_rate": self.invalid_rate,
            "metadata": dict(self.metadata),
        }


def evaluate_binary(y_true: np.ndarray, p: np.ndarray, *, threshold: float = 0.5) -> EvalReport:
    if len(y_true) == 0:
        return EvalReport(n=0, coverage=0.0, invalid_rate=1.0)
    p = np.clip(p.astype(float), 1e-6, 1 - 1e-6)
    pred = (p >= threshold).astype(int)
    acc = float(np.mean(pred == y_true))
    tp = float(np.sum((pred == 1) & (y_true == 1)))
    fp = float(np.sum((pred == 1) & (y_true == 0)))
    fn = float(np.sum((pred == 0) & (y_true == 1)))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    ll = float(-np.mean(y_true * np.log(p) + (1 - y_true) * np.log(1 - p)))
    br = float(np.mean((p - y_true) ** 2))
    return EvalReport(
        n=len(y_true),
        accuracy=acc,
        precision=precision,
        recall=recall,
        f1=f1,
        log_loss=ll,
        brier=br,
        coverage=1.0,
        invalid_rate=0.0,
    )
