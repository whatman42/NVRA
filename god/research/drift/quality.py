"""Data quality firewall — never silently clean meaning-changing issues."""

from __future__ import annotations

import math
from typing import Optional

from .models import DataQualityStatus, ObservationSeries


def assess_series_quality(
    series: Optional[ObservationSeries],
    *,
    min_samples: int = 1,
) -> tuple[DataQualityStatus, str]:
    """Return (status, reason). Does not mutate series."""
    if series is None:
        return DataQualityStatus.UNAVAILABLE, "series is None"
    if not series.values:
        return DataQualityStatus.INSUFFICIENT_DATA, "empty values"
    if len(series.values) < min_samples:
        return (
            DataQualityStatus.INSUFFICIENT_DATA,
            f"sample_size={len(series.values)} < min_samples={min_samples}",
        )

    for i, v in enumerate(series.values):
        if v is None:
            return DataQualityStatus.INVALID, f"null at index {i}"
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return DataQualityStatus.INVALID, f"nan/inf at index {i}"

    # temporal integrity
    if series.timestamps:
        if len(series.timestamps) != len(series.values):
            return (
                DataQualityStatus.INVALID,
                "timestamp length mismatch",
            )
        for i in range(1, len(series.timestamps)):
            if series.timestamps[i] < series.timestamps[i - 1]:
                return (
                    DataQualityStatus.INVALID,
                    f"chronology violation at index {i}",
                )
            if series.timestamps[i] == series.timestamps[i - 1]:
                return (
                    DataQualityStatus.INVALID,
                    f"duplicate timestamp at index {i}",
                )

    return DataQualityStatus.VALID, "ok"


def check_future_leakage(
    reference: ObservationSeries,
    current: ObservationSeries,
) -> Optional[str]:
    """Reject if current window starts before reference ends (when timestamps exist)."""
    if not reference.timestamps or not current.timestamps:
        return None  # cannot check without timestamps
    ref_max = max(reference.timestamps)
    cur_min = min(current.timestamps)
    if cur_min < ref_max:
        # allow overlap only if explicitly same — still flag strict future leakage
        # if any current point is before last reference point in a way that mixes
        overlapping = [t for t in current.timestamps if t <= ref_max]
        if overlapping and cur_min < ref_max:
            return f"future_leakage_or_overlap: cur_min={cur_min} ref_max={ref_max}"
    return None
