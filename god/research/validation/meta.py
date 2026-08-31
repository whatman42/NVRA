"""Validation metadata — evidence records, not live deployment permission."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ValidationMetadata:
    """OOS / walk-forward / robustness *records* without universal thresholds."""

    experiment_id: str
    oos_recorded: bool = False
    walk_forward_recorded: bool = False
    robustness_recorded: bool = False
    random_seed: Optional[int] = None
    methodology: Optional[str] = None
    dataset_identity: Optional[str] = None
    lineage: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "oos_recorded": self.oos_recorded,
            "walk_forward_recorded": self.walk_forward_recorded,
            "robustness_recorded": self.robustness_recorded,
            "random_seed": self.random_seed,
            "methodology": self.methodology,
            "dataset_identity": self.dataset_identity,
            "lineage": list(self.lineage),
            "notes": list(self.notes),
            "extra": dict(self.extra),
        }

    def as_flags(self) -> dict[str, bool]:
        return {
            "oos_recorded": self.oos_recorded,
            "walk_forward_recorded": self.walk_forward_recorded,
            "robustness_recorded": self.robustness_recorded,
        }


def record_validation(
    experiment_id: str,
    *,
    oos: bool = False,
    walk_forward: bool = False,
    robustness: bool = False,
    random_seed: Optional[int] = None,
    methodology: Optional[str] = None,
    dataset_identity: Optional[str] = None,
    lineage: Optional[list[str]] = None,
) -> ValidationMetadata:
    return ValidationMetadata(
        experiment_id=experiment_id,
        oos_recorded=oos,
        walk_forward_recorded=walk_forward,
        robustness_recorded=robustness,
        random_seed=random_seed,
        methodology=methodology,
        dataset_identity=dataset_identity,
        lineage=list(lineage or []),
        notes=["validation metadata only — not a promotion gate"],
    )
