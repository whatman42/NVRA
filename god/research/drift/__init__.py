"""Phase 4E — Drift detection (observation only). DETECT ≠ DECIDE."""

from .models import (
    DataQualityStatus,
    DriftAssessment,
    DriftCategory,
    EpistemicState,
    ObservationSeries,
)
from .quality import assess_series_quality, check_future_leakage
from .detectors import (
    DEFAULT_DETECTORS,
    FeatureDriftDetector,
    MeanShiftDetector,
    ResidualDriftDetector,
)
from .engine import DriftEngine

__all__ = [
    "DataQualityStatus",
    "DriftAssessment",
    "DriftCategory",
    "EpistemicState",
    "ObservationSeries",
    "assess_series_quality",
    "check_future_leakage",
    "DEFAULT_DETECTORS",
    "FeatureDriftDetector",
    "MeanShiftDetector",
    "ResidualDriftDetector",
    "DriftEngine",
]
