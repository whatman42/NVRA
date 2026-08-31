"""Evidence helpers for RCA chain integrity."""

from __future__ import annotations

from typing import Optional

from .models import CauseHypothesis, RootCauseAssessment
from .taxonomy import CausalStatus, CauseRole


def has_confirmed_root(assessment: RootCauseAssessment) -> bool:
    if assessment.primary_candidate is None:
        return False
    return (
        assessment.primary_candidate.role == CauseRole.CONFIRMED_ROOT_CAUSE
        and assessment.primary_candidate.causal_status == CausalStatus.CONFIRMED
    )


def require_evidence_for_confirmation(cause: CauseHypothesis) -> bool:
    """Confirmed status requires non-empty evidence_refs."""
    if cause.causal_status == CausalStatus.CONFIRMED:
        return len(cause.evidence_refs) > 0
    return True
