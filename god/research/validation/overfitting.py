"""Offline overfitting diagnostics: PBO and Deflated Sharpe Ratio."""
from __future__ import annotations
from dataclasses import dataclass
import math
from statistics import NormalDist

import numpy as np


@dataclass(frozen=True)
class PBOResult:
    probability: float
    logits: tuple[float, ...]
    observations: int


def probability_of_backtest_overfitting(train_scores: np.ndarray, test_scores: np.ndarray) -> PBOResult:
    """Estimate PBO from paired train/test scores.

    Rows are candidate configurations; columns are CPCV paths. For each path,
    the in-sample winner is selected and its out-of-sample rank is measured.
    PBO is the fraction of paths where that rank is below the median.
    """
    train = np.asarray(train_scores, dtype=float)
    test = np.asarray(test_scores, dtype=float)
    if train.shape != test.shape or train.ndim != 2:
        raise ValueError("train_scores and test_scores must be equal-shaped 2-D arrays")
    if train.shape[0] < 2 or train.shape[1] < 1:
        raise ValueError("at least two candidates and one path are required")
    winners = np.argmax(train, axis=0)
    logits: list[float] = []
    overfit = 0
    for col, winner in enumerate(winners):
        order = np.argsort(test[:, col], kind="mergesort")
        rank = int(np.where(order == winner)[0][0]) + 1
        p = rank / (train.shape[0] + 1.0)
        if p < 0.5:
            overfit += 1
        logits.append(math.log(p / (1.0 - p)))
    return PBOResult(overfit / len(logits), tuple(logits), len(logits))


def _skew(x: np.ndarray) -> float:
    mean = float(np.mean(x)); std = float(np.std(x, ddof=1))
    return 0.0 if std == 0 else float(np.mean(((x - mean) / std) ** 3))


def _kurtosis(x: np.ndarray) -> float:
    mean = float(np.mean(x)); std = float(np.std(x, ddof=1))
    return 0.0 if std == 0 else float(np.mean(((x - mean) / std) ** 4) - 3.0)


def deflated_sharpe_ratio(
    returns: np.ndarray,
    trials: int,
    *,
    benchmark_sharpe: float = 0.0,
    periods_per_year: float = 252.0,
) -> float:
    """Approximate DSR as a probability that the observed Sharpe exceeds a
    multiple-testing-adjusted hurdle. Designed for model governance, not
    intraday decisioning.
    """
    x = np.asarray(returns, dtype=float)
    if x.ndim != 1 or x.size < 3:
        raise ValueError("returns must contain at least 3 observations")
    if trials < 1 or periods_per_year <= 0:
        raise ValueError("trials must be >=1 and periods_per_year >0")
    sd = float(np.std(x, ddof=1))
    if sd == 0.0:
        return 0.0
    sr = float(np.mean(x) / sd * math.sqrt(periods_per_year))
    n = x.size
    skew = _skew(x)
    kurt = _kurtosis(x)
    se = math.sqrt(max(1e-12, (1 - skew * sr + ((kurt + 2) / 4.0) * sr * sr) / (n - 1)))
    # Expected maximum of `trials` standard normals, asymptotic approximation.
    q = NormalDist().inv_cdf(max(1e-12, min(1 - 1e-12, 1 - 1 / max(2, trials))))
    hurdle = benchmark_sharpe + se * q
    return float(NormalDist().cdf((sr - hurdle) / se))
