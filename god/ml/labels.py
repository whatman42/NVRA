"""Explicit horizon labels — no feature contamination, no fake labels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class LabelSpec:
    horizon: int = 1  # T+horizon bars
    name: str = "direction_t_plus_h"

    def __post_init__(self) -> None:
        if self.horizon < 1:
            raise ValueError("horizon must be >= 1")


def build_direction_labels(
    closes: Sequence[float],
    feature_indices: np.ndarray,
    *,
    spec: LabelSpec | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Label at index t uses close[t+horizon] vs close[t].
    Indices without enough future bars are dropped (not invented).
    Returns (y, valid_indices) aligned to feature rows that have labels.
    """
    spec = spec or LabelSpec(horizon=1)
    c = np.asarray(closes, dtype=float)
    y: list[int] = []
    valid: list[int] = []
    for t in feature_indices:
        t = int(t)
        h = t + spec.horizon
        if h >= len(c):
            continue
        if c[t] <= 0:
            continue
        r = c[h] / c[t] - 1.0
        y.append(1 if r > 0 else 0)
        valid.append(t)
    return np.asarray(y, dtype=int), np.asarray(valid, dtype=int)


