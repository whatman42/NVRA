"""Phase 4E — Drift models.

Drift = observed statistical/structural difference vs reference.
Descriptive evidence only. DETECT ≠ DECIDE. DRIFT ≠ FAILURE.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class DriftCategory(str, Enum):
    DATA_DRIFT = "DATA_DRIFT"
    FEATURE_DRIFT = "FEATURE_DRIFT"
    DISTRIBUTION_DRIFT = "DISTRIBUTION_DRIFT"
    RESIDUAL_DRIFT = "RESIDUAL_DRIFT"
    PERFORMANCE_DRIFT = "PERFORMANCE_DRIFT"
    EXECUTION_DRIFT = "EXECUTION_DRIFT"
    LATENCY_DRIFT = "LATENCY_DRIFT"
    LIQUIDITY_DRIFT = "LIQUIDITY_DRIFT"
    RELATIONSHIP_DRIFT = "RELATIONSHIP_DRIFT"
    CONCEPT_DRIFT = "CONCEPT_DRIFT"
    UNKNOWN_DRIFT = "UNKNOWN_DRIFT"


class EpistemicState(str, Enum):
    OBSERVED = "OBSERVED"
    SUSPECTED = "SUSPECTED"
    SUPPORTED = "SUPPORTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNKNOWN = "UNKNOWN"


class DataQualityStatus(str, Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ObservationSeries:
    """Injected observation series — no broker dependency."""

    name: str
    values: tuple[float, ...]
    timestamps: tuple[str, ...] = ()
    unit: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "values": list(self.values),
            "timestamps": list(self.timestamps),
            "unit": self.unit,
            "metadata": dict(self.metadata),
        }


@dataclass
class DriftAssessment:
    """Immutable historical record once registered."""

    assessment_id: str
    timestamp: str
    category: DriftCategory
    epistemic_state: EpistemicState
    detector_id: str
    detector_version: str
    methodology: str
    reference_window: Optional[str] = None
    observation_window: Optional[str] = None
    sample_size_ref: int = 0
    sample_size_cur: int = 0
    score: Optional[float] = None  # descriptive distance / change metric
    score_name: Optional[str] = None
    assumptions: list[str] = field(default_factory=list)
    multiple_testing_context: Optional[str] = None
    family_id: Optional[str] = None
    strategy_ref: Optional[str] = None
    experiment_ref: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    quality_status: DataQualityStatus = DataQualityStatus.UNKNOWN
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assessment_id": self.assessment_id,
            "timestamp": self.timestamp,
            "category": self.category.value,
            "epistemic_state": self.epistemic_state.value,
            "detector_id": self.detector_id,
            "detector_version": self.detector_version,
            "methodology": self.methodology,
            "reference_window": self.reference_window,
            "observation_window": self.observation_window,
            "sample_size_ref": self.sample_size_ref,
            "sample_size_cur": self.sample_size_cur,
            "score": self.score,
            "score_name": self.score_name,
            "assumptions": list(self.assumptions),
            "multiple_testing_context": self.multiple_testing_context,
            "family_id": self.family_id,
            "strategy_ref": self.strategy_ref,
            "experiment_ref": self.experiment_ref,
            "evidence_refs": list(self.evidence_refs),
            "quality_status": self.quality_status.value,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    def has_execution_intent(self) -> bool:
        blob = " ".join(
            [self.category.value, self.notes, str(list(self.metadata.keys()))]
        ).lower()
        return any(
            t in blob
            for t in (
                "op_buy",
                "op_sell",
                "ordersend",
                "lot_size",
                "allocate capital",
                "switch_strategy",
                "promote_strategy",
            )
        )


def make_drift_id(
    detector_id: str,
    category: DriftCategory,
    ref_hash: str,
    cur_hash: str,
    methodology: str,
) -> str:
    payload = {
        "d": detector_id,
        "c": category.value,
        "r": ref_hash,
        "u": cur_hash,
        "m": methodology,
    }
    return "drift-" + content_hash(payload)[:24]
