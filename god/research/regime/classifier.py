"""Deterministic regime classifier — descriptive labels only. REGIME ≠ SIGNAL."""

from __future__ import annotations

import math
from typing import Any, Optional

from god.research.drift.models import ObservationSeries
from god.research.drift.quality import assess_series_quality
from god.research.drift.models import DataQualityStatus

from .models import EvidenceQuality, RegimeLabel, UncertaintyLevel


def _mean(vals: tuple[float, ...]) -> float:
    return sum(vals) / len(vals) if vals else 0.0


def _std(vals: tuple[float, ...]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def classify_volatility(
    series: ObservationSeries,
    *,
    high_vol_std: Optional[float] = None,
    low_vol_std: Optional[float] = None,
    min_samples: int = 3,
) -> dict[str, Any]:
    """
    Classify HIGH_VOLATILITY / LOW_VOLATILITY / STABLE / UNKNOWN.

    Parameters high_vol_std / low_vol_std are detector configuration only —
    not universal trading laws. If not provided, uses relative comparison
    to series mean magnitude.
    """
    q, reason = assess_series_quality(series, min_samples=min_samples)
    if q != DataQualityStatus.VALID:
        return {
            "classification": RegimeLabel.UNKNOWN,
            "candidates": [RegimeLabel.UNKNOWN],
            "uncertainty": UncertaintyLevel.INSUFFICIENT_DATA,
            "evidence_quality": EvidenceQuality.EVIDENCE_MISSING,
            "notes": reason,
            "methodology": "volatility_std_relative",
        }

    std = _std(series.values)
    mean_abs = abs(_mean(series.values)) or 1.0
    rel = std / mean_abs

    # configuration defaults are relative ratios, recorded in notes
    hi = high_vol_std if high_vol_std is not None else 0.5
    lo = low_vol_std if low_vol_std is not None else 0.1

    candidates: list[RegimeLabel] = []
    if rel >= hi:
        primary = RegimeLabel.HIGH_VOLATILITY
        candidates = [RegimeLabel.HIGH_VOLATILITY, RegimeLabel.TRANSITION]
        unc = UncertaintyLevel.MODERATE
        eq = EvidenceQuality.EVIDENCE_PRESENT
    elif rel <= lo:
        primary = RegimeLabel.LOW_VOLATILITY
        candidates = [RegimeLabel.LOW_VOLATILITY, RegimeLabel.STABLE]
        unc = UncertaintyLevel.MODERATE
        eq = EvidenceQuality.EVIDENCE_PRESENT
    else:
        primary = RegimeLabel.STABLE
        candidates = [RegimeLabel.STABLE, RegimeLabel.RANGE_BOUND]
        unc = UncertaintyLevel.MODERATE
        eq = EvidenceQuality.EVIDENCE_PRESENT

    return {
        "classification": primary,
        "candidates": candidates,
        "uncertainty": unc,
        "evidence_quality": eq,
        "notes": f"rel_std={rel:.6f} hi={hi} lo={lo}",
        "methodology": "volatility_std_relative",
        "score": rel,
    }


def classify_unknown() -> dict[str, Any]:
    return {
        "classification": RegimeLabel.UNKNOWN,
        "candidates": [RegimeLabel.UNKNOWN],
        "uncertainty": UncertaintyLevel.UNKNOWN,
        "evidence_quality": EvidenceQuality.EVIDENCE_INCONCLUSIVE,
        "notes": "forced_unknown",
        "methodology": "explicit_unknown",
    }


def merge_conflicting(
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    """If multiple classifiers disagree → MIXED / CONFLICTING_EVIDENCE."""
    if not results:
        return classify_unknown()
    labels = {r["classification"] for r in results}
    if len(labels) == 1:
        return results[0]
    return {
        "classification": RegimeLabel.MIXED,
        "candidates": list(labels) + [RegimeLabel.MIXED],
        "uncertainty": UncertaintyLevel.HIGH,
        "evidence_quality": EvidenceQuality.CONFLICTING_EVIDENCE,
        "notes": f"conflicting labels: {[x.value if hasattr(x,'value') else x for x in labels]}",
        "methodology": "multi_classifier_merge",
    }
