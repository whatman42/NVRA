"""Evidence Registry and Independent Reviewer artifacts for N.U.N.G.

This package implements the durable, append-only evidence layer required by
the autonomous-quant-trading-systems Independent Reviewer protocol.

CLAIM ≠ EVIDENCE ≠ INTERPRETATION ≠ DECISION.
Finalized ReviewArtifacts are semantically immutable.
Corrections create new artifacts that reference prior ones.
"""

from .models import (
    EvidenceGrade,
    ImpactDomain,
    PromotionState,
    ReviewDecision,
    ReviewerMode,
    EvidenceClaim,
    ReviewArtifact,
)
from .registry import EvidenceRegistry

__all__ = [
    "EvidenceGrade",
    "ImpactDomain",
    "PromotionState",
    "ReviewDecision",
    "ReviewerMode",
    "EvidenceClaim",
    "ReviewArtifact",
    "EvidenceRegistry",
]
