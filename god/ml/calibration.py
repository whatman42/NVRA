"""Probability calibration — fit on VALIDATION only, never on test."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np


@dataclass
class CalibrationResult:
    status: str  # VALID | CALIBRATION_INVALID | SKIPPED
    method: str = "none"
    brier_before: float = 0.0
    brier_after: float = 0.0
    log_loss_before: float = 0.0
    log_loss_after: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "method": self.method,
            "brier_before": self.brier_before,
            "brier_after": self.brier_after,
            "log_loss_before": self.log_loss_before,
            "log_loss_after": self.log_loss_after,
            "metadata": dict(self.metadata),
        }


def _brier(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(np.mean((p - y) ** 2))


def _log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


@dataclass
class PlattCalibrator:
    """Simple sigmoid a*logit(p)+b fitted on validation probabilities only."""

    a: float = 1.0
    b: float = 0.0
    fitted: bool = False

    def fit(self, y_val: np.ndarray, p_val: np.ndarray) -> CalibrationResult:
        if len(y_val) < 10 or len(np.unique(y_val)) < 2:
            return CalibrationResult(status="CALIBRATION_INVALID", method="platt", metadata={"reason": "insufficient_val"})
        p = np.clip(p_val.astype(float), 1e-6, 1 - 1e-6)
        z = np.log(p / (1 - p))
        try:
            from sklearn.linear_model import LogisticRegression

            lr = LogisticRegression(max_iter=200, random_state=42)
            lr.fit(z.reshape(-1, 1), y_val)
            self.a = float(lr.coef_[0][0])
            self.b = float(lr.intercept_[0])
            self.fitted = True
            p_cal = self.transform(p_val)
            return CalibrationResult(
                status="VALID",
                method="platt",
                brier_before=_brier(y_val, p_val),
                brier_after=_brier(y_val, p_cal),
                log_loss_before=_log_loss(y_val, p_val),
                log_loss_after=_log_loss(y_val, p_cal),
            )
        except Exception as e:
            return CalibrationResult(status="CALIBRATION_INVALID", method="platt", metadata={"error": str(e)})

    def transform(self, p: np.ndarray) -> np.ndarray:
        if not self.fitted:
            return p
        p = np.clip(p.astype(float), 1e-6, 1 - 1e-6)
        z = np.log(p / (1 - p))
        s = self.a * z + self.b
        return 1.0 / (1.0 + np.exp(-s))


@dataclass
class IsotonicCalibrator:
    """Isotonic regression on validation probs — only when n is sufficient."""

    x_thresholds: list[float] = field(default_factory=list)
    y_thresholds: list[float] = field(default_factory=list)
    fitted: bool = False

    def fit(self, y_val: np.ndarray, p_val: np.ndarray) -> CalibrationResult:
        if len(y_val) < 50 or len(np.unique(y_val)) < 2:
            return CalibrationResult(
                status="CALIBRATION_INVALID",
                method="isotonic",
                metadata={"reason": "insufficient_val_for_isotonic"},
            )
        p = np.clip(np.asarray(p_val, dtype=float), 1e-6, 1 - 1e-6)
        y = np.asarray(y_val, dtype=float)
        try:
            from sklearn.isotonic import IsotonicRegression

            iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            iso.fit(p, y)
            self.x_thresholds = [float(v) for v in getattr(iso, "X_thresholds_", p)]
            self.y_thresholds = [float(v) for v in getattr(iso, "y_thresholds_", y)]
            if not self.x_thresholds:
                order = np.argsort(p)
                self.x_thresholds = [float(v) for v in p[order]]
                self.y_thresholds = [float(v) for v in y[order]]
            self.fitted = True
            p_cal = self.transform(p)
            return CalibrationResult(
                status="VALID",
                method="isotonic",
                brier_before=_brier(y, p),
                brier_after=_brier(y, p_cal),
                log_loss_before=_log_loss(y, p),
                log_loss_after=_log_loss(y, p_cal),
                metadata={"n": len(y)},
            )
        except Exception as e:
            return CalibrationResult(
                status="CALIBRATION_INVALID",
                method="isotonic",
                metadata={"error": str(e)},
            )

    def transform(self, p: np.ndarray) -> np.ndarray:
        if not self.fitted or not self.x_thresholds:
            return np.asarray(p, dtype=float)
        p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
        return np.interp(p, self.x_thresholds, self.y_thresholds)


def select_and_fit_calibrator(
    y_val: np.ndarray,
    p_val: np.ndarray,
    *,
    prefer_isotonic_min_n: int = 80,
) -> tuple[Any, CalibrationResult]:
    """Choose Platt (small n) or Isotonic (larger n). Always validation-only."""
    n = len(y_val)
    if n >= prefer_isotonic_min_n:
        iso = IsotonicCalibrator()
        result = iso.fit(y_val, p_val)
        if result.status == "VALID":
            return iso, result
    platt = PlattCalibrator()
    result = platt.fit(y_val, p_val)
    return platt, result
