"""Time-series splits — NEVER random shuffle for temporal data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

import numpy as np


@dataclass(frozen=True)
class TimeSeriesSplitSpec:
    n_splits: int = 3
    train_min: int = 50
    test_size: int = 20
    embargo: int = 1  # gap between train end and test start


def time_series_splits(
    n_samples: int,
    spec: TimeSeriesSplitSpec | None = None,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Yield (train_idx, test_idx) expanding/rolling windows without leakage."""
    spec = spec or TimeSeriesSplitSpec()
    if n_samples < spec.train_min + spec.test_size + spec.embargo:
        return

    # expanding window walk-forward
    start_test = spec.train_min + spec.embargo
    fold = 0
    while start_test + spec.test_size <= n_samples and fold < spec.n_splits:
        train_end = start_test - spec.embargo
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(start_test, start_test + spec.test_size)
        if len(train_idx) >= spec.train_min:
            yield train_idx, test_idx
            fold += 1
        start_test += spec.test_size
