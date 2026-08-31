"""Meta-labeling interface — primary signal + secondary take-signal model.

Backward-compatible and fail-closed: does not alter production signal behavior
unless an explicit meta model is attached and validation allows it.
Existing tests remain unaffected when meta is disabled (default).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from .prediction import Direction, Prediction, PredictionStatus
from .train import TrainedModel


@dataclass
class MetaLabelDecision:
    """Whether the primary signal should be taken."""

    take: bool
    meta_probability: float
    primary_direction: Direction
    reason: str = ""
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "take": self.take,
            "meta_probability": self.meta_probability,
            "primary_direction": self.primary_direction.value if hasattr(self.primary_direction, "value") else str(self.primary_direction),
            "reason": self.reason,
            "enabled": self.enabled,
        }


class MetaLabeler:
    """Optional meta-model wrapper. Default: passthrough (enabled=False)."""

    def __init__(
        self,
        meta_model: Optional[TrainedModel] = None,
        *,
        threshold: float = 0.55,
        enabled: bool = False,
    ) -> None:
        self.meta_model = meta_model
        self.threshold = threshold
        self.enabled = bool(enabled and meta_model is not None)

    def decide(
        self,
        primary: Prediction,
        features: Optional[np.ndarray] = None,
    ) -> MetaLabelDecision:
        if not self.enabled or self.meta_model is None:
            # Fail-closed / backward compatible: do not change behavior
            take = primary.status == PredictionStatus.VALID and primary.direction != Direction.NEUTRAL
            return MetaLabelDecision(
                take=take,
                meta_probability=1.0 if take else 0.0,
                primary_direction=primary.direction,
                reason="meta_disabled_passthrough",
                enabled=False,
            )

        if primary.status != PredictionStatus.VALID or primary.direction == Direction.NEUTRAL:
            return MetaLabelDecision(
                take=False,
                meta_probability=0.0,
                primary_direction=primary.direction,
                reason="primary_not_actionable",
                enabled=True,
            )

        if features is None or len(features) == 0:
            return MetaLabelDecision(
                take=False,
                meta_probability=0.0,
                primary_direction=primary.direction,
                reason="no_features_fail_closed",
                enabled=True,
            )

        try:
            X = np.asarray(features)
            if X.ndim == 1:
                X = X.reshape(1, -1)
            p = float(self.meta_model.predict_proba_positive(X[-1:])[0])
            take = p >= self.threshold
            return MetaLabelDecision(
                take=take,
                meta_probability=p,
                primary_direction=primary.direction,
                reason="meta_scored",
                enabled=True,
            )
        except Exception as e:
            return MetaLabelDecision(
                take=False,
                meta_probability=0.0,
                primary_direction=primary.direction,
                reason=f"meta_error_fail_closed:{type(e).__name__}",
                enabled=True,
            )

    def filter_prediction(
        self,
        primary: Prediction,
        features: Optional[np.ndarray] = None,
    ) -> Prediction:
        """Return primary unchanged when meta disabled; else neutralise if meta rejects."""
        decision = self.decide(primary, features)
        if not decision.enabled:
            return primary
        if decision.take:
            return primary
        # Fail-closed: force neutral without mutating original status semantics for evidence
        return Prediction(
            model_id=primary.model_id,
            model_version=primary.model_version,
            timestamp=primary.timestamp,
            symbol=primary.symbol,
            timeframe=primary.timeframe,
            direction=Direction.NEUTRAL,
            probability=0.5,
            confidence=0.0,
            features_version=primary.features_version,
            dataset_hash=primary.dataset_hash,
            horizon=primary.horizon,
            expected_return=0.0,
            regime=primary.regime,
            status=PredictionStatus.BLOCKED,
            metadata={**(primary.metadata or {}), "meta_label": decision.to_dict()},
        )
