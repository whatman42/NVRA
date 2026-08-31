"""Sample weighting — volatility / return-aware, never lets extremes dominate.

Used only at training time. Pure numpy. Fail-closed to uniform weights.
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np


def volatility_sample_weights(
    returns: Sequence[float] | np.ndarray,
    *,
    clip_percentile: float = 95.0,
    min_weight: float = 0.25,
    max_weight: float = 2.0,
) -> np.ndarray:
    """Inverse-volatility style weights with hard clipping.

    Extreme observations are down-weighted, not zeroed, to avoid bias.
    """
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n == 0:
        return np.asarray([], dtype=float)
    if n < 5:
        return np.ones(n, dtype=float)

    abs_r = np.abs(r)
    # Rolling local scale (causal-ish expanding)
    scale = np.maximum(np.std(abs_r), 1e-8)
    raw = 1.0 / (1.0 + abs_r / scale)

    # Soft-clip extremes via percentile on |return|
    lo = np.percentile(abs_r, 100.0 - clip_percentile)
    hi = np.percentile(abs_r, clip_percentile)
    # Points beyond hi get min_weight floor
    w = np.clip(raw, min_weight, max_weight)
    extreme = abs_r > hi
    w[extreme] = min_weight
    # Normalize to mean 1
    mean_w = float(np.mean(w)) or 1.0
    return (w / mean_w).astype(float)


def uniform_weights(n: int) -> np.ndarray:
    return np.ones(max(0, int(n)), dtype=float)


def apply_sample_weights(
    X: np.ndarray,
    y: np.ndarray,
    weights: Optional[np.ndarray] = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return X, y, w aligned; default uniform. Never drops rows."""
    n = len(y)
    if weights is None or len(weights) != n:
        w = uniform_weights(n)
    else:
        w = np.asarray(weights, dtype=float)
        w = np.where(np.isfinite(w) & (w > 0), w, 1.0)
        mean_w = float(np.mean(w)) or 1.0
        w = w / mean_w
    return X, y, w
