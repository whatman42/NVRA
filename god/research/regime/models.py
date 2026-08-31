"""Phase 4E — Regime evidence models.

Regime = observational classification. REGIME ≠ SIGNAL.
UNKNOWN / MIXED / TRANSITION are valid successful outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from god.memory.database import utc_now
from god.research.provenance import build_provenance, content_hash


class RegimeLabel(str, Enum):
    TRENDING = "TRENDING"
    RANGE_BOUND = "RANGE_BOUND"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    HIGH_LIQUIDITY = "HIGH_LIQUIDITY"
    LOW_LIQUIDITY = "LOW_LIQUIDITY"
    STABLE = "STABLE"
    TRANSITION = "TRANSITION"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class UncertaintyLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EvidenceQuality(str, Enum):
    EVIDENCE_PRESENT = "EVIDENCE_PRESENT"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    EVIDENCE_STALE = "EVIDENCE_STALE"
    EVIDENCE_INCONCLUSIVE = "EVIDENCE_INCONCLUSIVE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


@dataclass
class RegimeAssessment:
    regime_id: str
    timestamp: str
    classification: RegimeLabel
    candidate_labels: list[RegimeLabel] = field(default_factory=list)
    uncertainty: UncertaintyLevel = UncertaintyLevel.UNKNOWN
    evidence_quality: EvidenceQuality = EvidenceQuality.EVIDENCE_INCONCLUSIVE
    evidence_refs: list[str] = field(default_factory=list)
    observation_refs: list[str] = field(default_factory=list)
    methodology: str = ""
    detector_version: str = "1.0"
    strategy_ref: Optional[str] = None
    experiment_ref: Optional[str] = None
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime_id": self.regime_id,
            "timestamp": self.timestamp,
            "classification": self.classification.value,
            "candidate_labels": [c.value for c in self.candidate_labels],
            "uncertainty": self.uncertainty.value,
            "evidence_quality": self.evidence_quality.value,
            "evidence_refs": list(self.evidence_refs),
            "observation_refs": list(self.observation_refs),
            "methodology": self.methodology,
            "detector_version": self.detector_version,
            "strategy_ref": self.strategy_ref,
            "experiment_ref": self.experiment_ref,
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
            "metadata": dict(self.metadata),
        }

    def has_execution_intent(self) -> bool:
        blob = " ".join(
            [self.classification.value, self.notes, str(list(self.metadata.keys()))]
        ).lower()
        return any(
            t in blob
            for t in (
                "op_buy",
                "op_sell",
                "ordersend",
                "lot_size",
                "switch_strategy",
                "promote_strategy",
            )
        )


@dataclass
class RegimeTransition:
    transition_id: str
    timestamp: str
    previous_label: RegimeLabel
    current_label: RegimeLabel
    previous_regime_id: Optional[str] = None
    current_regime_id: Optional[str] = None
    evidence_refs: list[str] = field(default_factory=list)
    provenance: Optional[dict[str, Any]] = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "transition_id": self.transition_id,
            "timestamp": self.timestamp,
            "previous_label": self.previous_label.value,
            "current_label": self.current_label.value,
            "previous_regime_id": self.previous_regime_id,
            "current_regime_id": self.current_regime_id,
            "evidence_refs": list(self.evidence_refs),
            "provenance": dict(self.provenance) if self.provenance else None,
            "notes": self.notes,
        }


def make_regime_id(
    classification: RegimeLabel,
    methodology: str,
    obs_hash: str,
) -> str:
    payload = {"c": classification.value, "m": methodology, "o": obs_hash}
    return "regime-" + content_hash(payload)[:24]
