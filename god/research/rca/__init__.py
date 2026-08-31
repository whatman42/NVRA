"""Phase 4D — Failure Root-Cause Analysis (research / diagnostic only)."""

from .taxonomy import CausalStatus, CauseCategory, CauseRole
from .models import (
    CauseHypothesis,
    FailureEvent,
    FailureSeverity,
    FailureStatus,
    RootCauseAssessment,
)
from .engine import RCAEngine
from .evidence import has_confirmed_root, require_evidence_for_confirmation

__all__ = [
    "CausalStatus",
    "CauseCategory",
    "CauseRole",
    "CauseHypothesis",
    "FailureEvent",
    "FailureSeverity",
    "FailureStatus",
    "RootCauseAssessment",
    "RCAEngine",
    "has_confirmed_root",
    "require_evidence_for_confirmation",
]
