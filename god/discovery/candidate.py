"""Candidate construction — descriptive, no order fields."""

from __future__ import annotations

from typing import Any, Optional

from god.research.provenance import build_provenance, content_hash

from .models import (
    Candidate,
    EligibilityStatus,
    QualityStatus,
    make_candidate_id,
)


def build_candidate(
    instrument: str,
    *,
    strategy_ref: Optional[str] = None,
    quality_status: QualityStatus = QualityStatus.UNKNOWN,
    eligibility: EligibilityStatus = EligibilityStatus.UNKNOWN,
    evidence_refs: Optional[list[str]] = None,
    research_refs: Optional[list[str]] = None,
    validation_refs: Optional[list[str]] = None,
    drift_refs: Optional[list[str]] = None,
    regime_refs: Optional[list[str]] = None,
    policy_refs: Optional[list[str]] = None,
    capital_refs: Optional[list[str]] = None,
    uncertainty: str = "UNKNOWN",
    ranking_metadata: Optional[dict[str, Any]] = None,
    notes: str = "",
) -> Candidate:
    ev = list(evidence_refs or [])
    evidence_key = content_hash(
        {
            "ev": sorted(ev),
            "q": quality_status.value,
            "el": eligibility.value,
            "u": uncertainty,
        }
    )
    cid = make_candidate_id(instrument, strategy_ref, evidence_key)
    payload = {
        "candidate_id": cid,
        "instrument": instrument,
        "strategy_ref": strategy_ref,
        "eligibility": eligibility.value,
    }
    prov = build_provenance(origin="discovery_candidate", payload=payload)
    return Candidate(
        candidate_id=cid,
        instrument_ref=instrument.upper(),
        strategy_ref=strategy_ref,
        evidence_refs=ev,
        research_refs=list(research_refs or []),
        validation_refs=list(validation_refs or []),
        drift_refs=list(drift_refs or []),
        regime_refs=list(regime_refs or []),
        policy_refs=list(policy_refs or []),
        capital_refs=list(capital_refs or []),
        quality_status=quality_status,
        eligibility=eligibility,
        uncertainty=uncertainty,
        ranking_metadata=dict(ranking_metadata or {}),
        provenance={
            "provenance_id": prov.provenance_id,
            "content_hash": prov.content_hash,
            "origin": prov.origin,
        },
        content_hash=content_hash(payload),
        notes=notes,
    )
