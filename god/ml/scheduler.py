"""Training scheduler — operational eligibility for adaptive retraining.

Retrain only when eligibility events fire. Never continuous / every-tick.
Inference always prioritized. Under resource pressure: TRAINING = DEFER.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional
from .drift import DriftReport
from .hardware import ResourceGovernor

@dataclass
class RetrainDecision:
    eligible: bool
    reason: str
    priority: int = 0
    details: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]:
        return {"eligible": self.eligible, "reason": self.reason, "priority": self.priority, "details": dict(self.details)}

@dataclass
class SchedulerConfig:
    min_new_samples: int = 50
    min_hours_between: float = 6.0
    require_drift_or_degradation: bool = True
    performance_drop_threshold: float = 0.05
    regime_change_trigger: bool = True
    min_samples_absolute: int = 40

class TrainingScheduler:
    def __init__(self, governor: Optional[ResourceGovernor] = None, config: Optional[SchedulerConfig] = None) -> None:
        self.governor = governor or ResourceGovernor()
        self.config = config or SchedulerConfig()
        self._last_train_samples: int = 0
        self._last_train_ts: float = 0.0
        self._total_samples_seen: int = 0
        self._last_oos_accuracy: float = 0.5
        self._last_regime: str = ""
        self._deferred_count: int = 0

    def observe_samples(self, n: int) -> None:
        self._total_samples_seen = max(self._total_samples_seen, int(n))

    def mark_trained(self, n_samples: int, ts: float = 0.0, *, oos_accuracy: float = 0.5, regime: str = "") -> None:
        self._last_train_samples = int(n_samples)
        self._last_train_ts = float(ts)
        self._last_oos_accuracy = float(oos_accuracy)
        if regime:
            self._last_regime = regime
        self._deferred_count = 0

    def evaluate(self, *, current_samples: int = 0, now_ts: float = 0.0, drift: Optional[DriftReport] = None, current_oos_accuracy: Optional[float] = None, current_regime: str = "", force: bool = False) -> RetrainDecision:
        if force:
            if not self.governor.may_start_training():
                self._deferred_count += 1
                return RetrainDecision(eligible=False, reason="force_but_resource_pressure", details={"inference_priority": True, "deferred_count": self._deferred_count})
            return RetrainDecision(eligible=True, reason="forced", priority=10)
        if not self.governor.limits.training_allowed or not self.governor.may_start_training():
            self._deferred_count += 1
            return RetrainDecision(eligible=False, reason="resource_pressure_or_training_disabled", details={"inference_priority": True, "deferred_count": self._deferred_count})
        if current_samples < self.config.min_samples_absolute and self._last_train_samples == 0:
            return RetrainDecision(eligible=False, reason="absolute_min_samples_not_met", details={"current": current_samples, "min": self.config.min_samples_absolute})
        new_data = current_samples - self._last_train_samples
        if new_data < self.config.min_new_samples and self._last_train_samples > 0:
            severe_drift = drift is not None and getattr(drift, "retrain_eligible", False) and getattr(drift, "restrict_promotion", False)
            if not severe_drift:
                return RetrainDecision(eligible=False, reason="insufficient_new_data", details={"new_samples": new_data, "min": self.config.min_new_samples})
        if self._last_train_ts > 0 and now_ts > 0:
            hours = (now_ts - self._last_train_ts) / 3600.0
            if hours < self.config.min_hours_between:
                return RetrainDecision(eligible=False, reason="cooldown", details={"hours_since": hours, "min_hours": self.config.min_hours_between})
        if current_oos_accuracy is not None and self._last_train_samples > 0:
            drop = self._last_oos_accuracy - float(current_oos_accuracy)
            if drop >= self.config.performance_drop_threshold:
                return RetrainDecision(eligible=True, reason="performance_degradation", priority=7, details={"last_acc": self._last_oos_accuracy, "current_acc": float(current_oos_accuracy), "drop": drop})
        if self.config.regime_change_trigger and current_regime and self._last_regime and current_regime != self._last_regime and current_regime != "UNCERTAIN":
            return RetrainDecision(eligible=True, reason="regime_change", priority=4, details={"from": self._last_regime, "to": current_regime})
        if self.config.require_drift_or_degradation and drift is not None:
            if not drift.retrain_eligible and self._last_train_samples > 0:
                return RetrainDecision(eligible=False, reason="no_drift_or_degradation_trigger")
            if drift.retrain_eligible:
                return RetrainDecision(eligible=True, reason="drift_triggered", priority=5, details=drift.to_dict() if hasattr(drift, "to_dict") else {})
        if self._last_train_samples == 0:
            if current_samples >= self.config.min_samples_absolute:
                return RetrainDecision(eligible=True, reason="initial_train", priority=3)
            return RetrainDecision(eligible=False, reason="waiting_initial_data")
        if new_data >= self.config.min_new_samples and not self.config.require_drift_or_degradation:
            return RetrainDecision(eligible=True, reason="sufficient_new_data", priority=2)
        return RetrainDecision(eligible=False, reason="no_trigger")
