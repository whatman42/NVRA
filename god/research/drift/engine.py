"""Drift assessment engine — idempotent, historically immutable, evidence only."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash

from .detectors import DEFAULT_DETECTORS, DriftDetector
from .models import (
    DriftAssessment,
    DriftCategory,
    EpistemicState,
    ObservationSeries,
    make_drift_id,
)
from .quality import assess_series_quality


class DriftEngine:
    def __init__(self, detectors: Optional[dict[str, DriftDetector]] = None) -> None:
        self._detectors = dict(detectors or DEFAULT_DETECTORS)
        self._assessments: dict[str, DriftAssessment] = {}

    def register_detector(self, detector: DriftDetector) -> None:
        self._detectors[detector.detector_id] = detector

    def assess(
        self,
        reference: ObservationSeries,
        current: ObservationSeries,
        *,
        detector_id: str = "mean_shift",
        category: Optional[DriftCategory] = None,
        strategy_ref: Optional[str] = None,
        experiment_ref: Optional[str] = None,
        evidence_refs: Optional[list[str]] = None,
        family_id: Optional[str] = None,
        multiple_testing_context: Optional[str] = None,
        assumptions: Optional[list[str]] = None,
        reference_window: Optional[str] = None,
        observation_window: Optional[str] = None,
        notes: str = "",
        min_samples: int = 2,
    ) -> DriftAssessment:
        det = self._detectors.get(detector_id)
        if det is None:
            raise KeyError(f"unknown detector: {detector_id}")

        ref_hash = content_hash(list(reference.values))
        cur_hash = content_hash(list(current.values))
        result = det.detect(reference, current, min_samples=min_samples)
        cat = category or result.get("category") or DriftCategory.UNKNOWN_DRIFT
        if isinstance(cat, str):
            cat = DriftCategory(cat)

        aid = make_drift_id(
            det.detector_id, cat, ref_hash, cur_hash, det.methodology
        )
        if aid in self._assessments:
            return self._assessments[aid]  # RETURN_EXISTING

        state = result.get("epistemic_state", EpistemicState.UNKNOWN)
        if isinstance(state, str):
            state = EpistemicState(state)
        qstat = result.get("quality_status")
        from .models import DataQualityStatus

        if isinstance(qstat, str):
            qstat = DataQualityStatus(qstat)
        elif qstat is None:
            qstat = DataQualityStatus.UNKNOWN

        prov = build_provenance(
            origin="drift_assessment",
            payload={
                "assessment_id": aid,
                "detector": det.detector_id,
                "category": cat.value,
                "ref_hash": ref_hash,
                "cur_hash": cur_hash,
                "score": result.get("score"),
            },
        )
        assessment = DriftAssessment(
            assessment_id=aid,
            timestamp=utc_now(),
            category=cat,
            epistemic_state=state,
            detector_id=det.detector_id,
            detector_version=det.detector_version,
            methodology=det.methodology,
            reference_window=reference_window,
            observation_window=observation_window,
            sample_size_ref=int(result.get("sample_size_ref") or len(reference.values)),
            sample_size_cur=int(result.get("sample_size_cur") or len(current.values)),
            score=result.get("score"),
            score_name=result.get("score_name"),
            assumptions=list(assumptions or []),
            multiple_testing_context=multiple_testing_context,
            family_id=family_id,
            strategy_ref=strategy_ref,
            experiment_ref=experiment_ref,
            evidence_refs=list(evidence_refs or []),
            quality_status=qstat,
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            notes=notes or result.get("notes", ""),
            metadata={},
        )
        self._assessments[aid] = assessment
        return assessment

    def get(self, assessment_id: str) -> Optional[DriftAssessment]:
        return self._assessments.get(assessment_id)

    def list_all(self) -> list[DriftAssessment]:
        return list(self._assessments.values())

    def list_for_strategy(self, strategy_ref: str) -> list[DriftAssessment]:
        return [a for a in self._assessments.values() if a.strategy_ref == strategy_ref]
