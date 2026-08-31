"""Rich experiment metadata — bookkeeping only, no promotion gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ExperimentOutcomeExt(str, Enum):
    """Extended outcomes beyond 4A PASS/FAIL/ERROR/INCONCLUSIVE."""

    PASS = "PASS"
    FAIL = "FAIL"
    REJECTED = "REJECTED"
    INCONCLUSIVE = "INCONCLUSIVE"
    TIMEOUT = "TIMEOUT"
    INVALID = "INVALID"
    OVERFIT_FLAG = "OVERFIT_FLAG"
    ERROR = "ERROR"


@dataclass
class ExperimentMetadata:
    experiment_id: str
    hypothesis_id: Optional[str] = None
    dataset_ref: Optional[str] = None
    parameters: dict[str, Any] = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)
    random_seed: Optional[int] = None
    methodology: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    failure_reason: Optional[str] = None
    validation_flags: dict[str, bool] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    # Multiple-testing bookkeeping (not statistical law)
    family_id: Optional[str] = None
    family_size: int = 1
    rank_in_family: Optional[int] = None
    selection_bias_note: Optional[str] = None
    outcome: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "hypothesis_id": self.hypothesis_id,
            "dataset_ref": self.dataset_ref,
            "parameters": dict(self.parameters),
            "assumptions": list(self.assumptions),
            "random_seed": self.random_seed,
            "methodology": self.methodology,
            "result": dict(self.result) if self.result else None,
            "failure_reason": self.failure_reason,
            "validation_flags": dict(self.validation_flags),
            "provenance": dict(self.provenance),
            "family_id": self.family_id,
            "family_size": self.family_size,
            "rank_in_family": self.rank_in_family,
            "selection_bias_note": self.selection_bias_note,
            "outcome": self.outcome,
        }
