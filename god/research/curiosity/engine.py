"""CuriosityEngine — observation → anomalies → CuriosityEvents."""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import content_hash

from .detector import AnomalyDetector, Observation
from .models import AnomalyDescriptor, CuriosityEvent, Severity


class CuriosityEngine:
    def __init__(self, detector: Optional[AnomalyDetector] = None) -> None:
        self.detector = detector or AnomalyDetector()
        self._seen_ids: set[str] = set()
        self._events: list[CuriosityEvent] = []

    def process(
        self,
        observation: Observation,
        *,
        source: str = "observation",
        event_id: Optional[str] = None,
    ) -> list[CuriosityEvent]:
        """Produce curiosity events. Idempotent on explicit event_id."""
        eid_base = event_id or str(observation.get("observation_id") or uuid4())
        if event_id and event_id in self._seen_ids:
            return []

        anomalies = self.detector.detect(observation)
        if not anomalies:
            return []

        events: list[CuriosityEvent] = []
        obs_ref = str(observation.get("observation_id") or eid_base)
        for i, a in enumerate(anomalies):
            eid = event_id if (event_id and i == 0) else f"{eid_base}:{a.anomaly_type.value}:{i}"
            if eid in self._seen_ids:
                continue
            self._seen_ids.add(eid)
            prov = {
                "content_hash": content_hash(
                    {"observation": observation, "anomaly": a.to_dict()}
                ),
                "origin": "curiosity_engine",
            }
            ev = CuriosityEvent(
                event_id=eid,
                timestamp=utc_now(),
                source=source,
                anomaly_type=a.anomaly_type,
                severity=a.severity,
                evidence_refs=(),
                observation_refs=(obs_ref,),
                research_trigger=True,
                provenance=prov,
                description=f"Investigate {a.anomaly_type.value} anomaly",
                metadata={"score": a.score, "detail": a.detail},
            )
            self._events.append(ev)
            events.append(ev)
        if event_id:
            self._seen_ids.add(event_id)
        return events

    def list_events(self) -> list[CuriosityEvent]:
        return list(self._events)
