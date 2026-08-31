"""Regime transition evidence — never switches strategy or allocates capital."""

from __future__ import annotations

from typing import Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash

from .models import RegimeAssessment, RegimeLabel, RegimeTransition


def record_transition(
    previous: RegimeAssessment,
    current: RegimeAssessment,
    *,
    evidence_refs: Optional[list[str]] = None,
    notes: str = "",
) -> RegimeTransition:
    tid = "rtrans-" + content_hash(
        {
            "p": previous.regime_id,
            "c": current.regime_id,
            "pl": previous.classification.value,
            "cl": current.classification.value,
        }
    )[:24]
    prov = build_provenance(
        origin="regime_transition",
        payload={"transition_id": tid, "from": previous.classification.value, "to": current.classification.value},
    )
    return RegimeTransition(
        transition_id=tid,
        timestamp=utc_now(),
        previous_label=previous.classification,
        current_label=current.classification,
        previous_regime_id=previous.regime_id,
        current_regime_id=current.regime_id,
        evidence_refs=list(evidence_refs or []),
        provenance={
            "provenance_id": prov.provenance_id,
            "content_hash": prov.content_hash,
            "origin": prov.origin,
        },
        notes=notes or f"{previous.classification.value}→{current.classification.value}",
    )
