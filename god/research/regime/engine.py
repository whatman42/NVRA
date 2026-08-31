"""Regime assessment engine — evidence only, UNKNOWN valid, historically immutable."""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash
from god.research.drift.models import ObservationSeries

from .classifier import classify_unknown, classify_volatility, merge_conflicting
from .models import (
    EvidenceQuality,
    RegimeAssessment,
    RegimeLabel,
    RegimeTransition,
    UncertaintyLevel,
    make_regime_id,
)
from .transition import record_transition


class RegimeEngine:
    def __init__(self) -> None:
        self._assessments: dict[str, RegimeAssessment] = {}
        self._transitions: dict[str, RegimeTransition] = {}
        self._last_by_key: dict[str, str] = {}  # strategy/key → regime_id

    def classify(
        self,
        series: ObservationSeries,
        *,
        methodology: str = "volatility_std_relative",
        strategy_ref: Optional[str] = None,
        experiment_ref: Optional[str] = None,
        evidence_refs: Optional[list[str]] = None,
        observation_refs: Optional[list[str]] = None,
        high_vol_std: Optional[float] = None,
        low_vol_std: Optional[float] = None,
        min_samples: int = 3,
        notes: str = "",
        force_unknown: bool = False,
    ) -> RegimeAssessment:
        if force_unknown:
            result = classify_unknown()
        else:
            result = classify_volatility(
                series,
                high_vol_std=high_vol_std,
                low_vol_std=low_vol_std,
                min_samples=min_samples,
            )

        classification = result["classification"]
        if isinstance(classification, str):
            classification = RegimeLabel(classification)
        candidates = result.get("candidates") or [classification]
        candidates = [
            c if isinstance(c, RegimeLabel) else RegimeLabel(c) for c in candidates
        ]
        unc = result.get("uncertainty", UncertaintyLevel.UNKNOWN)
        if isinstance(unc, str):
            unc = UncertaintyLevel(unc)
        eq = result.get("evidence_quality", EvidenceQuality.EVIDENCE_INCONCLUSIVE)
        if isinstance(eq, str):
            eq = EvidenceQuality(eq)

        obs_hash = content_hash(list(series.values))
        rid = make_regime_id(classification, methodology, obs_hash)
        if rid in self._assessments:
            return self._assessments[rid]

        prov = build_provenance(
            origin="regime_assessment",
            payload={
                "regime_id": rid,
                "classification": classification.value,
                "methodology": methodology,
                "obs_hash": obs_hash,
            },
        )
        assessment = RegimeAssessment(
            regime_id=rid,
            timestamp=utc_now(),
            classification=classification,
            candidate_labels=list(candidates),
            uncertainty=unc,
            evidence_quality=eq,
            evidence_refs=list(evidence_refs or []),
            observation_refs=list(observation_refs or []),
            methodology=result.get("methodology", methodology),
            detector_version="1.0",
            strategy_ref=strategy_ref,
            experiment_ref=experiment_ref,
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            notes=notes or result.get("notes", ""),
            metadata={"score": result.get("score")},
        )
        self._assessments[rid] = assessment

        key = strategy_ref or "_global"
        prev_id = self._last_by_key.get(key)
        if prev_id and prev_id in self._assessments:
            prev = self._assessments[prev_id]
            if prev.classification != assessment.classification:
                tr = record_transition(prev, assessment, evidence_refs=evidence_refs)
                self._transitions[tr.transition_id] = tr
        self._last_by_key[key] = rid
        return assessment

    def classify_mixed(
        self,
        series_list: list[ObservationSeries],
        **kwargs: Any,
    ) -> RegimeAssessment:
        results = []
        for s in series_list:
            r = classify_volatility(s, min_samples=kwargs.get("min_samples", 3))
            results.append(r)
        merged = merge_conflicting(results)
        # build a synthetic series hash from all
        all_vals: list[float] = []
        for s in series_list:
            all_vals.extend(s.values)
        synthetic = ObservationSeries(name="mixed", values=tuple(all_vals))
        # reuse classify path with forced result via notes
        classification = merged["classification"]
        if isinstance(classification, str):
            classification = RegimeLabel(classification)
        obs_hash = content_hash(all_vals)
        rid = make_regime_id(classification, "multi_classifier_merge", obs_hash)
        if rid in self._assessments:
            return self._assessments[rid]
        from god.memory.database import utc_now

        prov = build_provenance(
            origin="regime_assessment",
            payload={"regime_id": rid, "classification": classification.value},
        )
        unc = merged.get("uncertainty", UncertaintyLevel.HIGH)
        if isinstance(unc, str):
            unc = UncertaintyLevel(unc)
        eq = merged.get("evidence_quality", EvidenceQuality.CONFLICTING_EVIDENCE)
        if isinstance(eq, str):
            eq = EvidenceQuality(eq)
        candidates = merged.get("candidates") or [classification]
        candidates = [
            c if isinstance(c, RegimeLabel) else RegimeLabel(c) for c in candidates
        ]
        a = RegimeAssessment(
            regime_id=rid,
            timestamp=utc_now(),
            classification=classification,
            candidate_labels=list(candidates),
            uncertainty=unc,
            evidence_quality=eq,
            evidence_refs=list(kwargs.get("evidence_refs") or []),
            observation_refs=[],
            methodology="multi_classifier_merge",
            detector_version="1.0",
            strategy_ref=kwargs.get("strategy_ref"),
            experiment_ref=kwargs.get("experiment_ref"),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            notes=merged.get("notes", ""),
        )
        self._assessments[rid] = a
        return a

    def get(self, regime_id: str) -> Optional[RegimeAssessment]:
        return self._assessments.get(regime_id)

    def list_all(self) -> list[RegimeAssessment]:
        return list(self._assessments.values())

    def list_transitions(self) -> list[RegimeTransition]:
        return list(self._transitions.values())
