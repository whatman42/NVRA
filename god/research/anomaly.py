"""Anomalous-source / data-poisoning heuristics (research safety, not strategy)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from .models import ProvenanceRecord, SourceProfile, SourceReliability
from .provenance import content_hash


@dataclass
class AnomalyReport:
    anomalous: bool
    reasons: list[str] = field(default_factory=list)
    content_hash: Optional[str] = None
    source_id: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "anomalous": self.anomalous,
            "reasons": list(self.reasons),
            "content_hash": self.content_hash,
            "source_id": self.source_id,
        }


class AnomalyDetector:
    """Detect duplicate floods, empty payloads, quarantined sources, hash clashes."""

    def __init__(self) -> None:
        self._seen_hashes: dict[str, int] = {}

    def inspect(
        self,
        payload: str | bytes | dict | list,
        *,
        source: Optional[SourceProfile] = None,
        provenance: Optional[ProvenanceRecord] = None,
        known_hashes: Optional[Sequence[str]] = None,
    ) -> AnomalyReport:
        reasons: list[str] = []
        h = content_hash(payload)

        if isinstance(payload, str) and not payload.strip():
            reasons.append("empty_payload")
        if isinstance(payload, (list, dict)) and len(payload) == 0:
            reasons.append("empty_structure")

        if source and source.reliability == SourceReliability.QUARANTINED:
            reasons.append("source_quarantined")

        count = self._seen_hashes.get(h, 0) + 1
        self._seen_hashes[h] = count
        if count >= 5:
            reasons.append("hash_flood")

        if known_hashes and h in known_hashes and count > 1:
            # same content re-ingested — informational, not always poison
            pass

        if provenance and provenance.content_hash != h:
            reasons.append("provenance_hash_mismatch")

        return AnomalyReport(
            anomalous=bool(reasons),
            reasons=reasons,
            content_hash=h,
            source_id=source.source_id if source else None,
        )
