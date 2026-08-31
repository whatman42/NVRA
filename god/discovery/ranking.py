"""Deterministic candidate ranking — discovery priority, NOT execution permission."""

from __future__ import annotations

from .models import Candidate, EligibilityStatus, QualityStatus


def _rank_key(c: Candidate) -> tuple:
    """
    Lower tuple sorts first (higher priority).
    Eligibility: ELIGIBLE > RESTRICTED > others
    Quality: VALID better
    Uncertainty: LOW better than HIGH/UNKNOWN
    Tie-break: candidate_id for determinism
    """
    el_order = {
        EligibilityStatus.ELIGIBLE: 0,
        EligibilityStatus.RESTRICTED: 1,
        EligibilityStatus.UNKNOWN: 2,
        EligibilityStatus.INSUFFICIENT_DATA: 3,
        EligibilityStatus.INELIGIBLE: 4,
        EligibilityStatus.BLOCKED: 5,
    }
    q_order = {
        QualityStatus.VALID: 0,
        QualityStatus.UNKNOWN: 1,
        QualityStatus.STALE: 2,
        QualityStatus.INSUFFICIENT_DATA: 3,
        QualityStatus.INVALID: 4,
    }
    unc = (c.uncertainty or "UNKNOWN").upper()
    unc_order = {"LOW": 0, "MODERATE": 1, "MEDIUM": 1, "HIGH": 2, "UNKNOWN": 3}.get(
        unc, 3
    )
    # optional descriptive score in ranking_metadata (config), not a trading law
    score = c.ranking_metadata.get("evidence_score")
    try:
        score_key = -float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        score_key = 0.0
    return (
        el_order.get(c.eligibility, 9),
        q_order.get(c.quality_status, 9),
        unc_order,
        score_key,
        c.instrument_ref,
        c.candidate_id,
    )


def rank_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Stable deterministic ranking. Does not grant execution permission."""
    return sorted(candidates, key=_rank_key)
