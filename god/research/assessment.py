"""Evidence assessment — descriptive scores only.

No fixed performance or risk thresholds as system law.
Callers may pass optional candidate weights for experiments; defaults are
neutral research heuristics.
"""

from __future__ import annotations

from typing import Optional, Sequence

from .models import (
    AssessmentResult,
    EvidenceRecord,
    SourceProfile,
    SourceReliability,
)


def assess_evidence(
    claim_id: str,
    evidence: Sequence[EvidenceRecord],
    *,
    source: Optional[SourceProfile] = None,
    contradicting: int = 0,
) -> AssessmentResult:
    """Compute a descriptive support score in [0, 1].

    Formula is intentionally simple and documented so it can itself be
    treated as a candidate hypothesis later — not hard-coded trading policy.
    """
    notes: list[str] = []
    supporting = len(evidence)
    if supporting == 0 and contradicting == 0:
        notes.append("no_evidence")
        return AssessmentResult(
            claim_id=claim_id,
            score=0.0,
            supporting=0,
            contradicting=contradicting,
            source_reliability=source.reliability if source else SourceReliability.UNKNOWN,
            notes=notes,
        )

    weight_sum = sum(max(0.0, e.weight) for e in evidence)
    raw = weight_sum / (weight_sum + max(0, contradicting) + 1e-9)
    # Soft-cap by source reliability (descriptive dampening)
    damp = 1.0
    rel = source.reliability if source else SourceReliability.UNKNOWN
    if rel == SourceReliability.QUARANTINED:
        damp = 0.0
        notes.append("source_quarantined_zeroed")
    elif rel == SourceReliability.LOW:
        damp = 0.5
        notes.append("source_low_damped")
    elif rel == SourceReliability.UNKNOWN:
        damp = 0.75
        notes.append("source_unknown_damped")
    score = max(0.0, min(1.0, raw * damp))
    return AssessmentResult(
        claim_id=claim_id,
        score=score,
        supporting=supporting,
        contradicting=contradicting,
        source_reliability=rel,
        notes=notes,
        metadata={"weight_sum": weight_sum},
    )
