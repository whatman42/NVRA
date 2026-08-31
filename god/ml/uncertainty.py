"""Uncertainty handling — confidence, OOD, optional conformal-style sets.

High uncertainty → NO_TRADE / BLOCK. Never forces a prediction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .ood import OODCheck, check_features


@dataclass
class UncertaintyReport:
    status: str  # OK | HIGH_UNCERTAINTY | OOD | BLOCK
    confidence: float = 0.0
    prediction_set: list[int] = field(default_factory=list)
    ood: Optional[OODCheck] = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confidence": self.confidence,
            "prediction_set": list(self.prediction_set),
            "ood": self.ood.to_dict() if self.ood and hasattr(self.ood, "to_dict") else None,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }

    @property
    def allow_trade(self) -> bool:
        return self.status == "OK"


def prediction_confidence(p: float) -> float:
    p = float(np.clip(p, 0.0, 1.0))
    return float(abs(p - 0.5) * 2.0)


def evaluate_uncertainty(
    p: float,
    *,
    X_row: Optional[np.ndarray] = None,
    baseline_X: Optional[np.ndarray] = None,
    min_confidence: float = 0.15,
    ood_block: bool = True,
) -> UncertaintyReport:
    conf = prediction_confidence(p)
    meta: dict[str, Any] = {"p": float(p)}

    ood_result: Optional[OODCheck] = None
    if X_row is not None:
        try:
            expected = None
            if baseline_X is not None and np.asarray(baseline_X).ndim == 2:
                expected = int(np.asarray(baseline_X).shape[1])
            ood_result = check_features(
                np.asarray(X_row).reshape(1, -1),
                expected_n_features=expected,
            )
            if ood_block and not ood_result.ok:
                return UncertaintyReport(
                    status="OOD",
                    confidence=conf,
                    prediction_set=[],
                    ood=ood_result,
                    reason=f"feature_ood:{ood_result.status}",
                    metadata=meta,
                )
        except Exception as e:
            meta["ood_error"] = str(e)

    if conf < min_confidence:
        return UncertaintyReport(
            status="HIGH_UNCERTAINTY",
            confidence=conf,
            prediction_set=[0, 1],
            ood=ood_result,
            reason="confidence_below_threshold",
            metadata={**meta, "min_confidence": min_confidence},
        )

    pred = 1 if p >= 0.5 else 0
    return UncertaintyReport(
        status="OK",
        confidence=conf,
        prediction_set=[pred],
        ood=ood_result,
        reason="ok",
        metadata=meta,
    )


