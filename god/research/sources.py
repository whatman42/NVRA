"""Source reliability tracking — quarantine on repeated anomalies."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from god.memory.database import utc_now

from .models import SourceProfile, SourceReliability


class SourceTracker:
    """In-process source profiles; optionally mirrored to audit via engine."""

    def __init__(self) -> None:
        self._sources: dict[str, SourceProfile] = {}

    def register(self, name: str, *, source_id: Optional[str] = None) -> SourceProfile:
        sid = source_id or str(uuid4())
        if sid in self._sources:
            return self._sources[sid]
        profile = SourceProfile(source_id=sid, name=name, last_seen=utc_now())
        self._sources[sid] = profile
        return profile

    def get(self, source_id: str) -> Optional[SourceProfile]:
        return self._sources.get(source_id)

    def list_sources(self) -> list[SourceProfile]:
        return list(self._sources.values())

    def record_success(self, source_id: str) -> SourceProfile:
        p = self._require(source_id)
        p.success_count += 1
        p.last_seen = utc_now()
        self._recompute(p)
        return p

    def record_failure(self, source_id: str) -> SourceProfile:
        p = self._require(source_id)
        p.failure_count += 1
        p.last_seen = utc_now()
        self._recompute(p)
        return p

    def record_anomaly(self, source_id: str) -> SourceProfile:
        p = self._require(source_id)
        p.anomaly_count += 1
        p.last_seen = utc_now()
        self._recompute(p)
        return p

    def _require(self, source_id: str) -> SourceProfile:
        if source_id not in self._sources:
            raise KeyError(f"unknown source_id: {source_id}")
        return self._sources[source_id]

    def _recompute(self, p: SourceProfile) -> None:
        # Descriptive tiers only — not trading law. Quarantine is safety for research data.
        if p.anomaly_count >= 3:
            p.reliability = SourceReliability.QUARANTINED
            return
        total = p.success_count + p.failure_count
        if total == 0:
            p.reliability = SourceReliability.UNKNOWN
            return
        ratio = p.success_count / total
        if ratio >= 0.8 and p.success_count >= 3:
            p.reliability = SourceReliability.HIGH
        elif ratio >= 0.5:
            p.reliability = SourceReliability.MEDIUM
        else:
            p.reliability = SourceReliability.LOW
