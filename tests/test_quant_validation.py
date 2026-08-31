import numpy as np
from god.research.validation import (
    combinatorial_purged_splits, number_of_paths,
    probability_of_backtest_overfitting, deflated_sharpe_ratio,
)


def test_cpcv_is_deterministic_and_embargoes():
    folds = combinatorial_purged_splits(60, 6, 2, 0.05)
    assert len(folds) == 15
    assert number_of_paths(6, 2) == 5
    for f in folds:
        assert set(f.train).isdisjoint(f.test)
        assert tuple(sorted(f.test)) == f.test


def test_cpcv_purges_overlapping_labels():
    ends = np.arange(20)
    ends[2] = 6
    folds = combinatorial_purged_splits(20, 4, 1, 0.0, ends)
    # A fold containing index 6 must purge label 2.
    fold = next(f for f in folds if 6 in f.test)
    assert 2 not in fold.train


def test_pbo_and_dsr_are_bounded():
    rng = np.random.default_rng(7)
    train = rng.normal(size=(8, 6))
    test = rng.normal(size=(8, 6))
    pbo = probability_of_backtest_overfitting(train, test)
    assert 0.0 <= pbo.probability <= 1.0
    dsr = deflated_sharpe_ratio(rng.normal(0.001, 0.01, 500), trials=20)
    assert 0.0 <= dsr <= 1.0
