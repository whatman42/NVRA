"""Drift detection — feature, prediction, performance, regime shift.

On drift: reduce confidence, restrict promotion, mark retrain eligible.
Never bypasses Risk Engine. Pure numpy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

import numpy as np

from .regime import Regime, detect_regime


@dataclass
class DriftReport:
    feature_drift: bool = False
    prediction_drift: bool = False
    performance_degraded: bool = False
    regime_shift: bool = False
    confidence_multiplier: float = 1.0
    retrain_eligible: bool = False
    restrict_promotion: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_drift": self.feature_drift,
            "prediction_drift": self.prediction_drift,
            "performance_degraded": self.performance_degraded,
            "regime_shift": self.regime_shift,
            "confidence_multiplier": self.confidence_multiplier,
            "retrain_eligible": self.retrain_eligible,
            "restrict_promotion": self.restrict_promotion,
            "details": dict(self.details),
        }


def _psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    """Population Stability Index (simple histogram)."""
    if len(expected) < 10 or len(actual) < 10:
        return 0.0
    lo = float(min(np.min(expected), np.min(actual)))
    hi = float(max(np.max(expected), np.max(actual)))
    if hi <= lo:
        return 0.0
    edges = np.linspace(lo, hi, bins + 1)
    e_hist, _ = np.histogram(expected, bins=edges)
    a_hist, _ = np.histogram(actual, bins=edges)
    e_pct = (e_hist + 1e-6) / (e_hist.sum() + 1e-6 * bins)
    a_pct = (a_hist + 1e-6) / (a_hist.sum() + 1e-6 * bins)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def detect_feature_drift(
    baseline_X: np.ndarray,
    recent_X: np.ndarray,
    *,
    psi_threshold: float = 0.25,
) -> tuple[bool, float]:
    if baseline_X is None or recent_X is None or len(baseline_X) < 10 or len(recent_X) < 5:
        return False, 0.0
    n_feat = min(baseline_X.shape[1], recent_X.shape[1])
    scores = []
    for j in range(n_feat):
        scores.append(_psi(baseline_X[:, j], recent_X[:, j]))
    max_psi = float(max(scores)) if scores else 0.0
    return max_psi >= psi_threshold, max_psi


def detect_prediction_drift(
    baseline_p: np.ndarray,
    recent_p: np.ndarray,
    *,
    mean_shift: float = 0.15,
) -> tuple[bool, float]:
    if len(baseline_p) < 10 or len(recent_p) < 5:
        return False, 0.0
    shift = abs(float(np.mean(recent_p)) - float(np.mean(baseline_p)))
    return shift >= mean_shift, shift


def detect_performance_degradation(
    baseline_acc: float,
    recent_acc: float,
    *,
    drop: float = 0.10,
) -> bool:
    if baseline_acc <= 0:
        return False
    return (baseline_acc - recent_acc) >= drop


def detect_regime_shift(
    closes_baseline: Sequence[float] | np.ndarray,
    closes_recent: Sequence[float] | np.ndarray,
) -> tuple[bool, str, str]:
    b = detect_regime(closes_baseline)
    r = detect_regime(closes_recent)
    shifted = b.regime != r.regime and r.regime != Regime.UNCERTAIN
    return shifted, b.regime.value, r.regime.value


def evaluate_drift(
    *,
    baseline_X: Optional[np.ndarray] = None,
    recent_X: Optional[np.ndarray] = None,
    baseline_p: Optional[np.ndarray] = None,
    recent_p: Optional[np.ndarray] = None,
    baseline_acc: float = 0.0,
    recent_acc: float = 0.0,
    closes_baseline: Optional[Sequence[float]] = None,
    closes_recent: Optional[Sequence[float]] = None,
) -> DriftReport:
    feat_drift, psi = (False, 0.0)
    if baseline_X is not None and recent_X is not None:
        feat_drift, psi = detect_feature_drift(baseline_X, recent_X)

    pred_drift, shift = (False, 0.0)
    if baseline_p is not None and recent_p is not None:
        pred_drift, shift = detect_prediction_drift(baseline_p, recent_p)

    perf = detect_performance_degradation(baseline_acc, recent_acc)

    reg_shift, from_r, to_r = (False, "", "")
    if closes_baseline is not None and closes_recent is not None:
        reg_shift, from_r, to_r = detect_regime_shift(closes_baseline, closes_recent)

    any_drift = feat_drift or pred_drift or perf or reg_shift
    conf = 1.0
    if any_drift:
        conf = 0.5 if (feat_drift or pred_drift) else 0.7
        if perf:
            conf = min(conf, 0.4)

    return DriftReport(
        feature_drift=feat_drift,
        prediction_drift=pred_drift,
        performance_degraded=perf,
        regime_shift=reg_shift,
        confidence_multiplier=conf,
        retrain_eligible=any_drift,
        restrict_promotion=any_drift,
        details={
            "psi": psi,
            "pred_mean_shift": shift,
            "baseline_acc": baseline_acc,
            "recent_acc": recent_acc,
            "regime_from": from_r,
            "regime_to": to_r,
        },
    )
