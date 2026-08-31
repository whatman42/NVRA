"""Phase 4D — Reality Gap models.

Reality Gap = expected/research/simulation vs observed outcome.
Descriptive evidence only — never trading policy or execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class GapDimension(str, Enum):
    """Descriptive gap dimensions — not trading rules."""

    DATA_GAP = "DATA_GAP"
    TIMING_GAP = "TIMING_GAP"
    EXECUTION_GAP = "EXECUTION_GAP"
    SLIPPAGE_GAP = "SLIPPAGE_GAP"
    SPREAD_GAP = "SPREAD_GAP"
    LIQUIDITY_GAP = "LIQUIDITY_GAP"
    MODEL_GAP = "MODEL_GAP"
    REGIME_GAP = "REGIME_GAP"
    ASSUMPTION_GAP = "ASSUMPTION_GAP"
    SIMULATION_GAP = "SIMULATION_GAP"
    OBSERVATION_GAP = "OBSERVATION_GAP"
    UNKNOWN_GAP = "UNKNOWN_GAP"


class ComparisonStatus(str, Enum):
    EQUAL = "EQUAL"
    POSITIVE_DELTA = "POSITIVE_DELTA"
    NEGATIVE_DELTA = "NEGATIVE_DELTA"
    MISSING_EXPECTED = "MISSING_EXPECTED"
    MISSING_OBSERVED = "MISSING_OBSERVED"
    INCOMPARABLE = "INCOMPARABLE"
    UNAVAILABLE = "UNAVAILABLE"


class AttributionStatus(str, Enum):
    PENDING = "PENDING"
    PARTIAL = "PARTIAL"
    ATTRIBUTED = "ATTRIBUTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MetricObservation:
    """Single expected or observed metric value."""

    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    source: Optional[str] = None
    timestamp: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "source": self.source,
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }


@dataclass
class RealityGap:
    """Typed reality-gap record. Evidence only — no universal 'bad' threshold."""

    gap_id: str
    timestamp: str
    dimension: GapDimension
    expected: Optional[MetricObservation] = None
    observed: Optional[MetricObservation] = None
    delta: Optional[float] = None
    relative_delta: Optional[float] = None
    comparison_status: ComparisonStatus = ComparisonStatus.UNAVAILABLE
    unit: Optional[str] = None
    strategy_ref: Optional[str] = None
    strategy_version: Optional[int] = None
    experiment_ref: Optional[str] = None
    expected_ref: Optional[str] = None
    observed_ref: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    confidence_as_evidence: Optional[str] = None  # descriptive, not a trading gate
    attribution_status: AttributionStatus = AttributionStatus.PENDING
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gap_id": self.gap_id,
            "timestamp": self.timestamp,
            "dimension": self.dimension.value,
            "expected": self.expected.to_dict() if self.expected else None,
            "observed": self.observed.to_dict() if self.observed else None,
            "delta": self.delta,
            "relative_delta": self.relative_delta,
            "comparison_status": self.comparison_status.value,
            "unit": self.unit,
            "strategy_ref": self.strategy_ref,
            "strategy_version": self.strategy_version,
            "experiment_ref": self.experiment_ref,
            "expected_ref": self.expected_ref,
            "observed_ref": self.observed_ref,
            "evidence_refs": list(self.evidence_refs),
            "provenance": dict(self.provenance) if self.provenance else None,
            "confidence_as_evidence": self.confidence_as_evidence,
            "attribution_status": self.attribution_status.value,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    def has_execution_intent(self) -> bool:
        blob = " ".join(
            [
                self.dimension.value,
                self.notes,
                str(list(self.metadata.keys())),
            ]
        ).lower()
        return any(
            t in blob
            for t in (
                "op_buy",
                "op_sell",
                "ordersend",
                "lot_size",
                "allocate capital",
                "broker_credential",
            )
        )


def make_gap_id(
    dimension: GapDimension,
    strategy_ref: Optional[str],
    experiment_ref: Optional[str],
    metric_name: str,
    expected_value: Optional[float],
    observed_value: Optional[float],
) -> str:
    """Deterministic id for idempotency."""
    payload = {
        "d": dimension.value,
        "s": strategy_ref or "",
        "e": experiment_ref or "",
        "m": metric_name,
        "ev": expected_value,
        "ov": observed_value,
    }
    return "gap-" + content_hash(payload)[:24]
