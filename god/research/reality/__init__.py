"""Phase 4D — Reality Gap (research / diagnostic only)."""

from .models import (
    AttributionStatus,
    ComparisonStatus,
    GapDimension,
    MetricObservation,
    RealityGap,
)
from .comparator import compare_metrics
from .engine import RealityGapEngine
from .attribution import mark_attributed, mark_unknown

__all__ = [
    "AttributionStatus",
    "ComparisonStatus",
    "GapDimension",
    "MetricObservation",
    "RealityGap",
    "compare_metrics",
    "RealityGapEngine",
    "mark_attributed",
    "mark_unknown",
]
