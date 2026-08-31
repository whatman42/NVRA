"""Opportunity ranking — cognitive attention priority, NOT trade priority."""

from __future__ import annotations

from .models import Compatibility, Opportunity, SelectionStatus, UncertaintyLevel


def _key(o: Opportunity) -> tuple:
    """Lower sorts first (higher attention)."""
    status_order = {
        SelectionStatus.SELECTED: 0,
        SelectionStatus.UNKNOWN: 1,
        SelectionStatus.INSUFFICIENT_EVIDENCE: 2,
        SelectionStatus.REJECTED: 3,
        SelectionStatus.BLOCKED: 4,
        SelectionStatus.NO_VALID_OPPORTUNITY: 5,
        SelectionStatus.PENDING: 6,
        SelectionStatus.EVALUATING: 6,
        SelectionStatus.COMPLETE: 6,
    }
    comp_order = {
        Compatibility.COMPATIBLE: 0,
        Compatibility.UNKNOWN: 1,
        Compatibility.INCOMPATIBLE: 2,
    }
    unc_order = {
        UncertaintyLevel.LOW: 0,
        UncertaintyLevel.MEDIUM: 1,
        UncertaintyLevel.HIGH: 2,
        UncertaintyLevel.UNKNOWN: 3,
    }
    disc = o.metadata.get("discovery_rank", 10**9)
    try:
        disc_i = int(disc)
    except (TypeError, ValueError):
        disc_i = 10**9
    return (
        status_order.get(o.selection_status, 9),
        comp_order.get(o.compatibility, 9),
        unc_order.get(o.uncertainty, 9),
        disc_i,
        o.opportunity_id,
    )


def rank_opportunities(items: list[Opportunity]) -> list[Opportunity]:
    """Stable deterministic ranking for cognitive attention."""
    ordered = sorted(items, key=_key)
    # re-assign attention_rank 0..n-1
    out: list[Opportunity] = []
    for i, o in enumerate(ordered):
        out.append(
            Opportunity(
                opportunity_id=o.opportunity_id,
                candidate_id=o.candidate_id,
                instrument_ref=o.instrument_ref,
                strategy_ref=o.strategy_ref,
                compatibility=o.compatibility,
                evidence_refs=o.evidence_refs,
                uncertainty=o.uncertainty,
                attention_rank=i,
                selection_status=o.selection_status,
                provenance=dict(o.provenance),
                content_hash=o.content_hash,
                notes=o.notes,
                metadata=dict(o.metadata),
            )
        )
    return out
