"""Deterministic expected vs observed comparison.

Produces deltas and status — never universal failure laws.
"""

from __future__ import annotations

from typing import Optional

from .models import ComparisonStatus, MetricObservation


def compare_metrics(
    expected: Optional[MetricObservation],
    observed: Optional[MetricObservation],
) -> tuple[ComparisonStatus, Optional[float], Optional[float], Optional[str]]:
    """
    Returns (status, delta, relative_delta, unit).

    relative_delta = (observed - expected) / |expected| when expected != 0.
    No threshold interpretation.
    """
    if expected is None and observed is None:
        return ComparisonStatus.UNAVAILABLE, None, None, None
    if expected is None:
        unit = observed.unit if observed else None
        return ComparisonStatus.MISSING_EXPECTED, None, None, unit
    if observed is None:
        return ComparisonStatus.MISSING_OBSERVED, None, None, expected.unit

    # unit mismatch → incomparable
    if expected.unit and observed.unit and expected.unit != observed.unit:
        return ComparisonStatus.INCOMPARABLE, None, None, None

    unit = expected.unit or observed.unit

    if expected.value is None and observed.value is None:
        return ComparisonStatus.UNAVAILABLE, None, None, unit
    if expected.value is None:
        return ComparisonStatus.MISSING_EXPECTED, None, None, unit
    if observed.value is None:
        return ComparisonStatus.MISSING_OBSERVED, None, None, unit

    delta = float(observed.value) - float(expected.value)
    rel: Optional[float] = None
    if abs(float(expected.value)) > 0:
        rel = delta / abs(float(expected.value))

    if delta == 0:
        status = ComparisonStatus.EQUAL
    elif delta > 0:
        status = ComparisonStatus.POSITIVE_DELTA
    else:
        status = ComparisonStatus.NEGATIVE_DELTA

    return status, delta, rel, unit
