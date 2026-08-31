"""Reality Gap Engine — expected vs observed → RealityGap records.

Idempotent by deterministic gap_id. No execution authority. No policy.
"""

from __future__ import annotations

from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance

from .comparator import compare_metrics
from .models import (
    AttributionStatus,
    GapDimension,
    MetricObservation,
    RealityGap,
    make_gap_id,
)


class RealityGapEngine:
    """Produces RealityGap evidence from expected/observed metric pairs."""

    def __init__(self) -> None:
        self._gaps: dict[str, RealityGap] = {}

    def record_gap(
        self,
        *,
        dimension: GapDimension,
        expected: Optional[MetricObservation] = None,
        observed: Optional[MetricObservation] = None,
        strategy_ref: Optional[str] = None,
        strategy_version: Optional[int] = None,
        experiment_ref: Optional[str] = None,
        expected_ref: Optional[str] = None,
        observed_ref: Optional[str] = None,
        evidence_refs: Optional[list[str]] = None,
        notes: str = "",
        confidence_as_evidence: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> RealityGap:
        metric_name = (
            (expected.name if expected else None)
            or (observed.name if observed else None)
            or "unknown"
        )
        ev = expected.value if expected else None
        ov = observed.value if observed else None
        gap_id = make_gap_id(
            dimension, strategy_ref, experiment_ref, metric_name, ev, ov
        )

        if gap_id in self._gaps:
            return self._gaps[gap_id]  # idempotent: return existing

        status, delta, rel, unit = compare_metrics(expected, observed)
        prov = build_provenance(
            origin="reality_gap",
            payload={
                "gap_id": gap_id,
                "dimension": dimension.value,
                "metric": metric_name,
                "expected": ev,
                "observed": ov,
                "status": status.value,
            },
            metadata={"strategy_ref": strategy_ref, "experiment_ref": experiment_ref},
        )
        gap = RealityGap(
            gap_id=gap_id,
            timestamp=utc_now(),
            dimension=dimension,
            expected=expected,
            observed=observed,
            delta=delta,
            relative_delta=rel,
            comparison_status=status,
            unit=unit,
            strategy_ref=strategy_ref,
            strategy_version=strategy_version,
            experiment_ref=experiment_ref,
            expected_ref=expected_ref,
            observed_ref=observed_ref,
            evidence_refs=list(evidence_refs or []),
            provenance={
                "provenance_id": prov.provenance_id,
                "content_hash": prov.content_hash,
                "origin": prov.origin,
            },
            confidence_as_evidence=confidence_as_evidence,
            attribution_status=AttributionStatus.PENDING,
            notes=notes,
            metadata=dict(metadata or {}),
        )
        self._gaps[gap_id] = gap
        return gap

    def get(self, gap_id: str) -> Optional[RealityGap]:
        return self._gaps.get(gap_id)

    def list_all(self) -> list[RealityGap]:
        return list(self._gaps.values())

    def list_for_strategy(self, strategy_ref: str) -> list[RealityGap]:
        return [g for g in self._gaps.values() if g.strategy_ref == strategy_ref]

    def list_for_experiment(self, experiment_ref: str) -> list[RealityGap]:
        return [g for g in self._gaps.values() if g.experiment_ref == experiment_ref]
