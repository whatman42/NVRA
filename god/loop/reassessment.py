"""Reassess attention items when evidence changes. No execution implications."""

from __future__ import annotations

from typing import Optional

from .evidence_fusion import apply_evidence_to_status
from .models import AttentionItem, AttentionStatus, EvidenceContext


def reassess_item(
    item: AttentionItem,
    evidence: EvidenceContext,
) -> AttentionItem:
    new_status_s, reason = apply_evidence_to_status(
        base_status=item.status.value,
        evidence=evidence,
    )
    try:
        new_status = AttentionStatus(new_status_s)
    except ValueError:
        new_status = AttentionStatus.UNKNOWN

    # map selected + degraded paths
    if item.status == AttentionStatus.SELECTED and new_status_s == "SELECTED":
        new_status = AttentionStatus.STILL_VALID
    if new_status_s == "DEGRADED":
        new_status = AttentionStatus.DEGRADED
    if new_status_s == "BLOCKED":
        new_status = AttentionStatus.BLOCKED
    if new_status_s == "UNKNOWN":
        new_status = AttentionStatus.UNKNOWN

    return AttentionItem(
        opportunity_id=item.opportunity_id,
        instrument_ref=item.instrument_ref,
        strategy_ref=item.strategy_ref,
        attention_priority=item.attention_priority,
        uncertainty=evidence.uncertainty or item.uncertainty,
        status=new_status,
        evidence_refs=list(dict.fromkeys(item.evidence_refs + evidence.evidence_refs)),
        drift_ref=evidence.drift_ref or item.drift_ref,
        regime_ref=evidence.regime_ref or item.regime_ref,
        reality_gap_ref=evidence.reality_gap_ref or item.reality_gap_ref,
        policy_ref=evidence.policy_ref or item.policy_ref,
        candidate_id=item.candidate_id,
        notes=f"{item.notes};reassess:{reason}".strip(";"),
        metadata=dict(item.metadata),
    )


def reassess_set(
    items: list[AttentionItem],
    evidence_by_instrument: dict[str, EvidenceContext],
    default_evidence: Optional[EvidenceContext] = None,
) -> list[AttentionItem]:
    out: list[AttentionItem] = []
    for it in items:
        ev = evidence_by_instrument.get(it.instrument_ref) or default_evidence
        if ev is None:
            out.append(it)
        else:
            out.append(reassess_item(it, ev))
    return out
