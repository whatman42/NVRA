"""Data-quality monitoring for Adaptive ML — continuous integrity checks.

Fail-closed: poor data quality restricts training / promotion and can force NO_TRADE.
Never enables LIVE or order_send.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import numpy as np


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class DataQualityReport:
    status: str  # OK | WARN | FAIL
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    restrict_training: bool = False
    restrict_promotion: bool = False
    prefer_no_trade: bool = False
    checked_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
            "restrict_training": self.restrict_training,
            "restrict_promotion": self.restrict_promotion,
            "prefer_no_trade": self.prefer_no_trade,
            "checked_at": self.checked_at,
        }


@dataclass
class DataQualityPolicy:
    max_nan_frac: float = 0.01
    max_inf_frac: float = 0.0
    min_class_frac: float = 0.05  # minority class share
    min_feature_std: float = 1e-8
    max_zero_var_frac: float = 0.25  # fraction of features with near-zero variance
    min_samples: int = 30
    max_duplicate_frac: float = 0.5


def evaluate_data_quality(
    X: np.ndarray,
    y: Optional[np.ndarray] = None,
    *,
    policy: Optional[DataQualityPolicy] = None,
) -> DataQualityReport:
    """Evaluate matrix / label integrity. Deterministic, no side effects."""
    policy = policy or DataQualityPolicy()
    reasons: list[str] = []
    metrics: dict[str, float] = {}
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 2:
        return DataQualityReport(
            status="FAIL",
            reasons=["invalid_shape"],
            restrict_training=True,
            restrict_promotion=True,
            prefer_no_trade=True,
            checked_at=_utc_now(),
        )

    n, nf = int(X.shape[0]), int(X.shape[1])
    metrics["n_samples"] = float(n)
    metrics["n_features"] = float(nf)

    if n < policy.min_samples:
        reasons.append("insufficient_samples")
    if nf < 1:
        reasons.append("no_features")

    finite = np.isfinite(X)
    nan_frac = float(1.0 - finite.mean()) if n * nf > 0 else 1.0
    inf_frac = float(np.isinf(X).mean()) if n * nf > 0 else 0.0
    metrics["nan_frac"] = nan_frac
    metrics["inf_frac"] = inf_frac
    if nan_frac > policy.max_nan_frac:
        reasons.append("high_nan_frac")
    if inf_frac > policy.max_inf_frac:
        reasons.append("has_inf")

    # Feature variance collapse
    if n >= 2 and nf >= 1:
        stds = np.nanstd(X, axis=0)
        zero_var = float(np.mean(stds < policy.min_feature_std))
        metrics["zero_var_frac"] = zero_var
        metrics["mean_feature_std"] = float(np.nanmean(stds))
        if zero_var > policy.max_zero_var_frac:
            reasons.append("feature_variance_collapse")
    else:
        metrics["zero_var_frac"] = 1.0
        metrics["mean_feature_std"] = 0.0

    # Class balance
    if y is not None:
        yy = np.asarray(y).ravel()
        if len(yy) == n and n > 0:
            vals, counts = np.unique(yy.astype(int), return_counts=True)
            total = float(counts.sum())
            min_frac = float(counts.min() / total) if total > 0 else 0.0
            metrics["min_class_frac"] = min_frac
            metrics["n_classes"] = float(len(vals))
            if min_frac < policy.min_class_frac:
                reasons.append("class_imbalance")
            if len(vals) < 2:
                reasons.append("single_class")

    # Approximate duplicate rows (cheap hash of rounded values)
    if n >= 4 and nf >= 1:
        try:
            rounded = np.round(X, decimals=6)
            fp = rounded[:, 0] * 1e6 + (rounded.sum(axis=1) if nf > 1 else 0)
            uniq = len(np.unique(fp))
            dup_frac = 1.0 - (uniq / n)
            metrics["duplicate_frac"] = float(dup_frac)
            if dup_frac > policy.max_duplicate_frac:
                reasons.append("high_duplicate_frac")
        except Exception:
            metrics["duplicate_frac"] = 0.0

    status = "OK"
    restrict_train = False
    restrict_promo = False
    no_trade = False

    hard = {"insufficient_samples", "no_features", "has_inf", "single_class", "invalid_shape"}
    soft = {"high_nan_frac", "feature_variance_collapse", "class_imbalance", "high_duplicate_frac"}

    if any(r in hard for r in reasons):
        status = "FAIL"
        restrict_train = True
        restrict_promo = True
        no_trade = True
    elif any(r in soft for r in reasons):
        status = "WARN"
        restrict_promo = True
        if "high_nan_frac" in reasons or "feature_variance_collapse" in reasons:
            restrict_train = True
            no_trade = True

    return DataQualityReport(
        status=status,
        reasons=reasons,
        metrics=metrics,
        restrict_training=restrict_train,
        restrict_promotion=restrict_promo,
        prefer_no_trade=no_trade,
        checked_at=_utc_now(),
    )
