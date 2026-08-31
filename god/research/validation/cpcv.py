"""Leakage-aware CPCV utilities for offline model governance.

Pure, deterministic utilities. Never imported by the daily execution path.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Sequence

import numpy as np


@dataclass(frozen=True)
class Fold:
    train: tuple[int, ...]
    test: tuple[int, ...]


def combinatorial_purged_splits(
    n_samples: int,
    n_groups: int = 6,
    n_test_groups: int = 2,
    embargo_pct: float = 0.0,
    label_end: Sequence[int] | None = None,
) -> tuple[Fold, ...]:
    """Return deterministic CPCV folds with optional label-aware purging.

    ``label_end[i]`` is the last sample index whose information contributes to
    label ``i``. Samples whose label interval overlaps a test interval are
    purged from training; an embargo is then applied after each test block.
    """
    if n_samples < 2 or n_groups < 2:
        raise ValueError("n_samples and n_groups must be >= 2")
    if not 1 <= n_test_groups < n_groups:
        raise ValueError("n_test_groups must be in [1, n_groups)")
    if not 0.0 <= embargo_pct < 1.0:
        raise ValueError("embargo_pct must be in [0, 1)")
    if label_end is not None and len(label_end) != n_samples:
        raise ValueError("label_end length must equal n_samples")

    groups = np.array_split(np.arange(n_samples, dtype=int), n_groups)
    embargo = int(np.ceil(n_samples * embargo_pct))
    folds: list[Fold] = []
    ends = np.asarray(label_end if label_end is not None else np.arange(n_samples), dtype=int)
    if np.any(ends < np.arange(n_samples)) or np.any(ends >= n_samples):
        raise ValueError("label_end must satisfy i <= label_end[i] < n_samples")

    for selected in combinations(range(n_groups), n_test_groups):
        test = np.concatenate([groups[i] for i in selected])
        test_set = set(test.tolist())
        train_mask = np.ones(n_samples, dtype=bool)
        train_mask[test] = False
        # Purge every training observation whose label interval intersects test.
        for i in np.flatnonzero(train_mask):
            start, end = i, int(ends[i])
            if any(start <= int(j) <= end or start <= int(ends[j]) <= end for j in test):
                train_mask[i] = False
        # Post-test embargo.
        for j in test:
            train_mask[int(j) + 1 : min(n_samples, int(j) + 1 + embargo)] = False
        train = np.flatnonzero(train_mask)
        folds.append(Fold(tuple(train.tolist()), tuple(sorted(test.tolist()))))
    return tuple(folds)


def number_of_paths(n_groups: int, n_test_groups: int) -> int:
    """Number of unique CPCV backtest paths, ``C(N,K) * K / N``."""
    if not 1 <= n_test_groups < n_groups:
        raise ValueError("n_test_groups must be in [1, n_groups)")
    from math import comb
    return comb(n_groups, n_test_groups) * n_test_groups // n_groups
