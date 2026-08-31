"""Feature engineering — causal lag only (no lookahead)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class FeatureSchema:
    version: str = "feat-v1"
    names: tuple[str, ...] = (
        "ret_1",
        "ret_5",
        "vol_5",
        "range_5",
        "close_z_20",
    )


def build_feature_matrix(
    closes: Sequence[float],
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    *,
    schema: FeatureSchema | None = None,
) -> tuple[np.ndarray, np.ndarray, FeatureSchema]:
    """
    Build features at index t using only data <= t.
    Labels (next return sign) are produced separately for training.
    Returns X[n_samples, n_features], valid_indices.
    """
    schema = schema or FeatureSchema()
    c = np.asarray(closes, dtype=float)
    n = len(c)
    if n < 25:
        return np.zeros((0, len(schema.names))), np.zeros(0, dtype=int), schema

    h = np.asarray(highs if highs is not None else c, dtype=float)
    l = np.asarray(lows if lows is not None else c, dtype=float)

    rows = []
    idxs = []
    for t in range(20, n):
        ret_1 = (c[t] / c[t - 1] - 1.0) if c[t - 1] else 0.0
        ret_5 = (c[t] / c[t - 5] - 1.0) if c[t - 5] else 0.0
        window = c[t - 4 : t + 1]
        vol_5 = float(np.std(np.diff(window) / np.maximum(window[:-1], 1e-12)))
        range_5 = float(np.max(h[t - 4 : t + 1]) - np.min(l[t - 4 : t + 1]))
        w20 = c[t - 19 : t + 1]
        mu, sig = float(np.mean(w20)), float(np.std(w20) + 1e-12)
        close_z = (c[t] - mu) / sig
        rows.append([ret_1, ret_5, vol_5, range_5, close_z])
        idxs.append(t)

    X = np.asarray(rows, dtype=float)
    return X, np.asarray(idxs, dtype=int), schema


def next_direction_labels(closes: Sequence[float], indices: np.ndarray) -> np.ndarray:
    """Label = sign of next return (using t+1). Last index cannot be labeled."""
    c = np.asarray(closes, dtype=float)
    y = []
    valid = []
    for t in indices:
        if t + 1 >= len(c):
            continue
        r = c[t + 1] / c[t] - 1.0 if c[t] else 0.0
        y.append(1 if r > 0 else 0)
        valid.append(t)
    return np.asarray(y, dtype=int), np.asarray(valid, dtype=int)
