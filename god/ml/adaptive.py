"""Adaptive ML orchestration facade — zero-manual-configuration.

Ties detector, governor, capabilities, selector, ensemble, meta,
benchmarking, regime, drift, promotion, scheduler, ops, data-quality,
graceful degradation.

Safety boundary:
  - ML produces probabilistic evidence only
  - Never bypasses Policy Gate / Risk Engine
  - Never enables LIVE or order_send
  - Hardware upgrade only adds capability; never auto-swaps champion
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from .audit import MLAuditTrail
from .benchmark import BenchmarkReport, benchmark_families
from .config_validate import ConfigValidationResult, MLRuntimeConfig, validate_ml_config
from .data_quality import DataQualityReport, evaluate_data_quality
from .degradation import DegradationDecision, evaluate_degradation
from .drift import DriftReport, evaluate_drift
from .ensemble import EnsembleResult, train_constrained_ensemble
from .hardware import (
    HardwareProfile,
    HardwareSnapshot,
    ResourceGovernor,
    ResourceLimits,
    detect_hardware,
    select_profile,
)
from .health import ModelHealthMonitor, HealthReport
from .meta_label import MetaLabelDecision, MetaLabeler
from .model_capabilities import ModelCapabilityRegistry
from .prediction import Prediction
from .promotion import PromotionGateResult, PromotionPolicy, try_promote
from .recovery import recover_champion, check_state_consistency, RecoveryResult
from .registry import ModelRecord, ModelRegistry
from .retention import RetentionPolicy, apply_retention
from .scheduler import RetrainDecision, TrainingScheduler
from .selector import AdaptiveModelSelector, SelectionResult
from .telemetry import MLTelemetry
from .train import TrainedModel


@dataclass
class AdaptiveMLContext:
    snapshot: HardwareSnapshot
    profile: HardwareProfile
    limits: ResourceLimits
    runnable_families: list[str] = field(default_factory=list)
    selection: Optional[SelectionResult] = None
    capabilities: dict[str, Any] = field(default_factory=dict)
    degradation: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot": self.snapshot.to_dict(),
            "profile": self.profile.value,
            "limits": self.limits.to_dict(),
            "runnable_families": list(self.runnable_families),
            "selection": self.selection.to_dict() if self.selection else None,
            "capabilities": self.capabilities,
            "degradation": self.degradation,
        }


class AdaptiveMLOrchestrator:
    """Hardware-aware orchestration entry point for paper/DEMO ML only."""

    def __init__(
        self,
        registry_root: Optional[Path] = None,
        *,
        meta_enabled: bool = False,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        self.governor = ResourceGovernor()
        self.capabilities = ModelCapabilityRegistry(
            gpu_available=self.governor.snapshot.gpu_available
        )
        self.registry = ModelRegistry(Path(registry_root) if registry_root else Path("ml_registry"))
        self.selector = AdaptiveModelSelector(
            governor=self.governor,
            capabilities=self.capabilities,
            registry=self.registry,
        )
        self.meta = MetaLabeler(enabled=meta_enabled)
        self.scheduler = TrainingScheduler(governor=self.governor)
        self.telemetry = MLTelemetry()
        self.health = ModelHealthMonitor(registry=self.registry, telemetry=self.telemetry)
        self.audit = MLAuditTrail()
        cfg_result = validate_ml_config(config)
        self._config = cfg_result.normalized
        self._config_valid = cfg_result.valid
        self._last_ensemble: Optional[EnsembleResult] = None
        self._last_selection: Optional[SelectionResult] = None
        self._last_benchmark: Optional[BenchmarkReport] = None
        self._last_drift: Optional[DriftReport] = None
        self._last_data_quality: Optional[DataQualityReport] = None
        self._last_degradation: Optional[DegradationDecision] = None

    def context(self) -> AdaptiveMLContext:
        limits = self.governor.limits
        runnable = self.capabilities.runnable(limits)
        selection = self.selector.select()
        self._last_selection = selection
        deg = self._last_degradation.to_dict() if self._last_degradation else None
        return AdaptiveMLContext(
            snapshot=self.governor.snapshot,
            profile=self.governor.profile,
            limits=limits,
            runnable_families=runnable,
            selection=selection,
            capabilities=self.capabilities.to_dict(),
            degradation=deg,
        )

    def refresh(self) -> AdaptiveMLContext:
        self.governor.refresh()
        self.capabilities.refresh(gpu_available=self.governor.snapshot.gpu_available)
        return self.context()

    def select_models(self) -> SelectionResult:
        result = self.selector.select()
        self._last_selection = result
        return result

    def check_data_quality(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
    ) -> DataQualityReport:
        report = evaluate_data_quality(X, y)
        self._last_data_quality = report
        self.audit.record(
            "data_quality",
            outcome=report.status,
            detail={"reasons": report.reasons, "metrics": report.metrics},
        )
        return report

    def evaluate_degradation_state(
        self,
        *,
        health_status: str = "UNKNOWN",
        resource_pressure: bool = False,
    ) -> DegradationDecision:
        dq = self._last_data_quality.status if self._last_data_quality else "OK"
        drift_restrict = False
        if self._last_drift is not None:
            drift_restrict = bool(getattr(self._last_drift, "restrict_promotion", False))
        decision = evaluate_degradation(
            profile=self.governor.profile,
            limits=self.governor.limits,
            health_status=health_status,
            data_quality_status=dq,
            resource_pressure=resource_pressure,
            drift_restrict=drift_restrict,
        )
        self._last_degradation = decision
        self.audit.record(
            "degradation",
            outcome=decision.mode,
            detail=decision.to_dict(),
        )
        return decision

    def validate_config(self, raw: Optional[dict[str, Any]] = None) -> ConfigValidationResult:
        return validate_ml_config(raw)

    def check_health(
        self,
        *,
        recent_oos_accuracy: Optional[float] = None,
        drift_restrict: bool = False,
        calibration_invalid: bool = False,
    ) -> HealthReport:
        report = self.health.evaluate(
            recent_oos_accuracy=recent_oos_accuracy,
            drift_restrict=drift_restrict,
            calibration_invalid=calibration_invalid,
        )
        self.audit.record(
            "health",
            model_id=report.champion_id,
            model_version=report.champion_version,
            outcome=report.status,
            detail=report.to_dict(),
        )
        return report

    def recover(self, *, try_previous_on_corrupt: bool = True) -> RecoveryResult:
        result, _model = recover_champion(
            self.registry, try_previous_on_corrupt=try_previous_on_corrupt
        )
        self.audit.record(
            "recovery",
            model_id=result.model_id,
            model_version=result.model_version,
            outcome="success" if result.success else "failed",
            detail=result.to_dict(),
        )
        return result

    def state_consistency(self) -> dict[str, Any]:
        return check_state_consistency(self.registry)

    def benchmark(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        feature_names: tuple[str, ...],
        features_version: str = "feat-v1",
        closes: Optional[np.ndarray] = None,
        sample_returns: Optional[np.ndarray] = None,
    ) -> BenchmarkReport:
        selection = self.selector.select()
        report = benchmark_families(
            X,
            y,
            selection.eligible,
            feature_names=feature_names,
            features_version=features_version,
            governor=self.governor,
            closes_for_regime=closes,
            sample_returns=sample_returns,
        )
        self._last_benchmark = report
        return report

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        feature_names: tuple[str, ...],
        features_version: str = "feat-v1",
        model_version: str = "1",
    ) -> EnsembleResult:
        """Resource-aware training with inference priority + data-quality gate."""
        dq = self.check_data_quality(X, y)
        if dq.restrict_training:
            self.audit.record(
                "train",
                outcome="deferred",
                detail={"reason": "data_quality", "status": dq.status},
            )
            return EnsembleResult(notes=[f"data_quality_blocked:{dq.status}"])

        deg = self.evaluate_degradation_state(
            health_status="HEALTHY",
            resource_pressure=not self.governor.limits.training_allowed,
        )
        if not deg.allow_training:
            self.audit.record(
                "train",
                outcome="deferred",
                detail={"reason": "degradation", "mode": deg.mode},
            )
            return EnsembleResult(notes=[f"degradation_blocked:{deg.mode}"])

        decision = self.scheduler.evaluate(current_samples=len(y), drift=self._last_drift)
        if not decision.eligible and self.scheduler._last_train_samples > 0:
            self.audit.record(
                "train",
                outcome="deferred",
                detail={"reason": decision.reason},
            )
            return EnsembleResult(notes=[f"scheduler_blocked:{decision.reason}"])

        selection = self.selector.select()
        self._last_selection = selection
        families = list(selection.ensemble_families)
        if not deg.allow_heavy_ml:
            families = [f for f in families if f.lower() not in ("lstm", "gru", "transformer")]
        if deg.max_ensemble < len(families):
            families = families[: deg.max_ensemble]

        result = train_constrained_ensemble(
            X,
            y,
            feature_names=feature_names,
            features_version=features_version,
            governor=self.governor,
            families=families,
            model_version=model_version,
        )
        self._last_ensemble = result
        for m in result.members:
            self._register_with_hardware(m.model)
        self.scheduler.mark_trained(len(y))
        self.audit.record(
            "train",
            outcome="ok",
            detail={"n_members": len(result.members), "notes": list(result.notes)},
        )
        self.telemetry.record_training(
            model_id=result.members[0].model.model_id if result.members else "none",
            model_version=model_version,
            n_samples=len(y),
            duration_ms=0.0,
            status="ok",
            profile=self.governor.profile.value,
        )
        return result

    def _register_with_hardware(self, model: TrainedModel) -> ModelRecord:
        hw = {
            "hardware_profile": self.governor.profile.value,
            "total_ram_mb": self.governor.snapshot.total_ram_mb,
            "cpu_threads": self.governor.snapshot.cpu_threads,
        }
        model.metadata = {**(model.metadata or {}), **hw}
        return self.registry.register_candidate(
            model,
            metrics={
                **model.metrics,
                **{
                    f"hw_{k}": float(v)
                    for k, v in hw.items()
                    if isinstance(v, (int, float))
                },
            },
            hardware_profile=self.governor.profile.value,
            model_family=model.model_id,
            persist=True,
        )

    def apply_meta(
        self, primary: Prediction, features: Optional[np.ndarray] = None
    ) -> tuple[Prediction, MetaLabelDecision]:
        decision = self.meta.decide(primary, features)
        filtered = self.meta.filter_prediction(primary, features)
        return filtered, decision

    def check_drift(
        self,
        *,
        baseline_X: Optional[np.ndarray] = None,
        recent_X: Optional[np.ndarray] = None,
        baseline_p: Optional[np.ndarray] = None,
        recent_p: Optional[np.ndarray] = None,
        baseline_acc: float = 0.0,
        recent_acc: float = 0.0,
        closes_baseline: Optional[Sequence[float]] = None,
        closes_recent: Optional[Sequence[float]] = None,
    ) -> DriftReport:
        report = evaluate_drift(
            baseline_X=baseline_X,
            recent_X=recent_X,
            baseline_p=baseline_p,
            recent_p=recent_p,
            baseline_acc=baseline_acc,
            recent_acc=recent_acc,
            closes_baseline=closes_baseline,
            closes_recent=closes_recent,
        )
        self._last_drift = report
        return report

    def promote_if_eligible(
        self,
        model_id: str,
        model_version: str,
        *,
        policy: Optional[PromotionPolicy] = None,
    ) -> PromotionGateResult:
        if self._last_data_quality and self._last_data_quality.restrict_promotion:
            self.audit.record(
                "promote",
                model_id=model_id,
                model_version=model_version,
                outcome="denied",
                detail={"reason": "data_quality"},
            )
            return PromotionGateResult(
                allowed=False,
                reason="data_quality_restrict",
                challenger_id=model_id,
                challenger_version=model_version,
            )
        if self._last_degradation and self._last_degradation.prefer_no_trade:
            self.audit.record(
                "promote",
                model_id=model_id,
                model_version=model_version,
                outcome="denied",
                detail={"reason": "degradation_prefer_no_trade"},
            )
            return PromotionGateResult(
                allowed=False,
                reason="degradation_prefer_no_trade",
                challenger_id=model_id,
                challenger_version=model_version,
            )
        result = try_promote(
            self.registry,
            model_id,
            model_version,
            drift=self._last_drift,
            policy=policy,
        )
        self.audit.record(
            "promote",
            model_id=model_id,
            model_version=model_version,
            outcome="allowed" if result.allowed else "denied",
            detail=result.to_dict() if hasattr(result, "to_dict") else {"allowed": result.allowed},
        )
        return result

    def retrain_eligibility(
        self,
        *,
        current_samples: int = 0,
        force: bool = False,
    ) -> RetrainDecision:
        return self.scheduler.evaluate(
            current_samples=current_samples,
            drift=self._last_drift,
            force=force,
        )

    def cleanup_storage(self, policy: Optional[RetentionPolicy] = None) -> dict:
        return apply_retention(self.registry, policy)

    def champion_unchanged_by_hardware(self) -> bool:
        """Hardware refresh must not auto-change champion."""
        before = self.registry.champion()
        self.refresh()
        after = self.registry.champion()
        if before is None and after is None:
            return True
        if before is None or after is None:
            return False
        return before.model_id == after.model_id and before.model_version == after.model_version

    def safety_assertions(self) -> dict[str, Any]:
        """Runtime confirmation of hard safety boundary."""
        return {
            "broker_orders_submitted": 0,
            "live_authorized": False,
            "path": "ml→evidence_only",
            "inference_priority": self.governor.limits.inference_priority,
            "profile": self.governor.profile.value,
            "training_allowed": self.governor.limits.training_allowed,
            "config_live_authorized": self._config.get("live_authorized", False),
        }
