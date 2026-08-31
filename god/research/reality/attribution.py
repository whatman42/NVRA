"""Descriptive attribution helpers for RealityGap records.

Attribution is evidence labeling, not causal proof or trading policy.
"""

from __future__ import annotations

from typing import Optional

from .models import AttributionStatus, RealityGap


def mark_attributed(
    gap: RealityGap,
    *,
    status: AttributionStatus = AttributionStatus.ATTRIBUTED,
    note: Optional[str] = None,
) -> RealityGap:
    gap.attribution_status = status
    if note:
        gap.notes = (gap.notes + " | " + note).strip(" |")
    return gap


def mark_unknown(gap: RealityGap, note: str = "insufficient_attribution") -> RealityGap:
    gap.attribution_status = AttributionStatus.UNKNOWN
    gap.notes = (gap.notes + " | " + note).strip(" |")
    return gap
