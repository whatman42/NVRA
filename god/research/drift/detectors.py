"""Pluggable drift detectors — deterministic, injectable, descriptive only.

No universal threshold laws. Scores are evidence, not policy.
"""

from __future__ import annotations

import math
from typing import Any, Optional, Protocol

from .models import DriftCategory, ObservationSeries
from .quality import assess_series_quality, check_future_leakage
from .models import DataQualityStatus, EpistemicState


class DriftDetector(Protocol):
    detector_id: str
    detector_version: str
    methodology: str

    def detect(
        self,
        reference: ObservationSeries,
        current: ObservationSeries,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Return dict with score, score_name, epistemic_state, quality_status, notes."""
        ...


def _mean(vals: tuple[float, ...]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: tuple[float, ...]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    var = sum((x - m) ** 2 for x in vals) / (len(vals) - 1)
    return math.sqrt(var)


class MeanShiftDetector:
    """Compares means of reference vs current. Descriptive distance only."""

    detector_id = "mean_shift"
    detector_version = "1.0"
    methodology = "absolute_mean_difference"

    def detect(
        self,
        reference: ObservationSeries,
        current: ObservationSeries,
        **kwargs: Any,
    ) -> dict[str, Any]:
        q_ref, r_ref = assess_series_quality(reference, min_samples=kwargs.get("min_samples", 2))
        q_cur, r_cur = assess_series_quality(current, min_samples=kwargs.get("min_samples", 2))
        if q_ref != DataQualityStatus.VALID:
            return {
                "score": None,
                "score_name": "mean_abs_diff",
                "epistemic_state": EpistemicState.INSUFFICIENT_DATA,
                "quality_status": q_ref,
                "notes": f"reference: {r_ref}",
                "category": DriftCategory.DISTRIBUTION_DRIFT,
            }
        if q_cur != DataQualityStatus.VALID:
            return {
                "score": None,
                "score_name": "mean_abs_diff",
                "epistemic_state": EpistemicState.INSUFFICIENT_DATA,
                "quality_status": q_cur,
                "notes": f"current: {r_cur}",
                "category": DriftCategory.DISTRIBUTION_DRIFT,
            }
        leak = check_future_leakage(reference, current)
        if leak:
            return {
                "score": None,
                "score_name": "mean_abs_diff",
                "epistemic_state": EpistemicState.INCONCLUSIVE,
                "quality_status": DataQualityStatus.INVALID,
                "notes": leak,
                "category": DriftCategory.DISTRIBUTION_DRIFT,
            }
        score = abs(_mean(current.values) - _mean(reference.values))
        # epistemic: score is descriptive; non-zero → SUSPECTED, zero → OBSERVED equal
        if score == 0.0:
            state = EpistemicState.OBSERVED
            notes = "means identical"
        else:
            state = EpistemicState.SUSPECTED
            notes = f"mean_shift={score}"
        return {
            "score": score,
            "score_name": "mean_abs_diff",
            "epistemic_state": state,
            "quality_status": DataQualityStatus.VALID,
            "notes": notes,
            "category": DriftCategory.DISTRIBUTION_DRIFT,
            "sample_size_ref": len(reference.values),
            "sample_size_cur": len(current.values),
        }


class FeatureDriftDetector:
    """Per-feature mean shift; category FEATURE_DRIFT."""

    detector_id = "feature_mean_shift"
    detector_version = "1.0"
    methodology = "per_feature_mean_abs_diff"

    def detect(
        self,
        reference: ObservationSeries,
        current: ObservationSeries,
        **kwargs: Any,
    ) -> dict[str, Any]:
        base = MeanShiftDetector().detect(reference, current, **kwargs)
        base["category"] = DriftCategory.FEATURE_DRIFT
        return base


class ResidualDriftDetector:
    """Compares residual series (caller supplies residual values)."""

    detector_id = "residual_mean_shift"
    detector_version = "1.0"
    methodology = "residual_mean_abs_diff"

    def detect(
        self,
        reference: ObservationSeries,
        current: ObservationSeries,
        **kwargs: Any,
    ) -> dict[str, Any]:
        base = MeanShiftDetector().detect(reference, current, **kwargs)
        base["category"] = DriftCategory.RESIDUAL_DRIFT
        return base


DEFAULT_DETECTORS: dict[str, DriftDetector] = {
    "mean_shift": MeanShiftDetector(),
    "feature_mean_shift": FeatureDriftDetector(),
    "residual_mean_shift": ResidualDriftDetector(),
}
