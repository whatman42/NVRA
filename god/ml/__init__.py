"""ML production pipeline for GOD/NVRA — research → prediction → evidence only.

NEVER submits broker orders. Persistence supports reload after restart.
Hardware-adaptive orchestration: zero manual config across 8 GB → 32 GB+ hosts.
Phase-2: benchmarking, regime, drift, promotion gates, sample weighting, scheduler.
Phase-3: dataset governance, rollback, calibration, uncertainty, scheduler triggers.
Ops: telemetry, health monitoring, audit trail, crash/restart recovery.
Ops-2: data-quality monitoring, config validation, graceful degradation.
Lifecycle: artifact integrity, checksum, schema compatibility, atomic persist.
Hardening: artifact manifest, integrity-verified rollback.
Reliability: state machine, transactional promotion, enhanced recovery, health score, freshness.
"""

from .prediction import Prediction, Direction, PredictionStatus
from .features import FeatureSchema, build_feature_matrix
from .split import TimeSeriesSplitSpec, time_series_splits
from .registry import ModelRegistry, ModelRecord
from .walk_forward import WalkForwardEngine, WalkForwardResult
from .train import train_baseline_classifier
from .risk_gate import MLRiskGate, RiskGateDecision
from .pipeline import MLPipeline, PipelineResult
from .labels import LabelSpec, build_direction_labels
from .calibration import PlattCalibrator, IsotonicCalibrator, CalibrationResult, select_and_fit_calibrator
from .evaluate import evaluate_binary, EvalReport
from .ood import check_features, OODCheck
from .evidence import MLEvidence, evidence_from_prediction
from .persist import (
    ArtifactBundle,
    save_trained_model,
    load_trained_model,
    load_trained_model_safe,
    validate_artifact_bundle,
)
from .hardware import (
    HardwareProfile,
    HardwareSnapshot,
    ResourceLimits,
    ResourceGovernor,
    detect_hardware,
    select_profile,
    build_resource_limits,
)
from .model_capabilities import (
    ModelFamilyCapability,
    ModelCapabilityRegistry,
    detect_model_capabilities,
    allowed_families_for_limits,
)
from .ensemble import EnsembleMember, EnsembleResult, train_constrained_ensemble
from .meta_label import MetaLabelDecision, MetaLabeler
from .retention import RetentionPolicy, apply_retention
from .selector import AdaptiveModelSelector, SelectionResult
from .adaptive import AdaptiveMLOrchestrator, AdaptiveMLContext
from .regime import Regime, RegimeSnapshot, detect_regime, regime_masks
from .weighting import volatility_sample_weights, uniform_weights, apply_sample_weights
from .drift import DriftReport, evaluate_drift
from .feature_eval import FeatureImportanceReport, evaluate_features, PROTECTED_FEATURES
from .benchmark import (
    BenchmarkMetrics,
    FamilyBenchmark,
    BenchmarkReport,
    benchmark_family,
    benchmark_families,
)
from .promotion import (
    PromotionGateResult,
    PromotionPolicy,
    RollbackResult,
    TransactionalPromotionResult,
    evaluate_promotion,
    try_promote,
    transactional_promote,
    evaluate_rollback,
    try_rollback,
)
from .scheduler import RetrainDecision, SchedulerConfig, TrainingScheduler
from .dataset import (
    DatasetSnapshot,
    build_dataset_snapshot,
    compute_matrix_checksum,
    detect_leakage,
    validate_snapshot,
)
from .uncertainty import evaluate_uncertainty, prediction_confidence
from .telemetry import MLTelemetry, InferenceEvent, TrainingEvent, TelemetrySummary
from .health import ModelHealthMonitor, HealthReport, HealthPolicy, compute_health_score
from .audit import MLAuditTrail, AuditEntry
from .recovery import recover_champion, recover_startup, check_state_consistency, RecoveryResult
from .data_quality import DataQualityReport, DataQualityPolicy, evaluate_data_quality
from .config_validate import (
    ConfigValidationResult,
    MLRuntimeConfig,
    validate_ml_config,
)
from .degradation import DegradationDecision, evaluate_degradation
from .lifecycle import (
    ARTIFACT_SCHEMA_VERSION,
    IntegrityReport,
    CompatibilityReport,
    verify_artifact_integrity,
    check_schema_compatibility,
    load_with_integrity,
    atomic_write_text,
    atomic_write_bytes,
)
from .manifest import (
    ArtifactManifest,
    MANIFEST_VERSION,
    build_manifest_from_bundle,
    validate_manifest,
    save_manifest,
    load_manifest,
    verify_manifest_against_disk,
    feature_schema_hash,
)
from .rollback_safe import SafeRollbackResult, safe_rollback
from .state_machine import (
    TransitionResult,
    is_legal_transition,
    validate_transition,
    apply_transition,
    LEGAL_TRANSITIONS,
)
from .freshness import (
    FreshnessReport,
    FreshnessPolicy,
    evaluate_freshness,
)

__all__ = [
    "Prediction", "Direction", "PredictionStatus", "FeatureSchema", "build_feature_matrix",
    "TimeSeriesSplitSpec", "time_series_splits", "ModelRegistry", "ModelRecord",
    "WalkForwardEngine", "WalkForwardResult", "train_baseline_classifier",
    "MLRiskGate", "RiskGateDecision", "MLPipeline", "PipelineResult",
    "LabelSpec", "build_direction_labels", "PlattCalibrator", "IsotonicCalibrator",
    "CalibrationResult", "select_and_fit_calibrator", "evaluate_binary", "EvalReport",
    "check_features", "OODCheck", "MLEvidence", "evidence_from_prediction",
    "ArtifactBundle", "save_trained_model", "load_trained_model", "load_trained_model_safe",
    "validate_artifact_bundle", "HardwareProfile", "HardwareSnapshot", "ResourceLimits",
    "ResourceGovernor", "detect_hardware", "select_profile", "build_resource_limits",
    "ModelFamilyCapability", "ModelCapabilityRegistry", "detect_model_capabilities",
    "allowed_families_for_limits", "EnsembleMember", "EnsembleResult", "train_constrained_ensemble",
    "MetaLabelDecision", "MetaLabeler", "RetentionPolicy", "apply_retention",
    "AdaptiveModelSelector", "SelectionResult", "AdaptiveMLOrchestrator", "AdaptiveMLContext",
    "Regime", "RegimeSnapshot", "detect_regime", "regime_masks",
    "volatility_sample_weights", "uniform_weights", "apply_sample_weights",
    "DriftReport", "evaluate_drift", "FeatureImportanceReport", "evaluate_features", "PROTECTED_FEATURES",
    "BenchmarkMetrics", "FamilyBenchmark", "BenchmarkReport", "benchmark_family", "benchmark_families",
    "PromotionGateResult", "PromotionPolicy", "RollbackResult", "TransactionalPromotionResult",
    "evaluate_promotion", "try_promote", "transactional_promote", "evaluate_rollback", "try_rollback",
    "RetrainDecision", "SchedulerConfig", "TrainingScheduler",
    "DatasetSnapshot", "build_dataset_snapshot", "compute_matrix_checksum", "detect_leakage", "validate_snapshot",
    "evaluate_uncertainty", "prediction_confidence",
    "MLTelemetry", "InferenceEvent", "TrainingEvent", "TelemetrySummary",
    "ModelHealthMonitor", "HealthReport", "HealthPolicy", "compute_health_score",
    "MLAuditTrail", "AuditEntry",
    "recover_champion", "recover_startup", "check_state_consistency", "RecoveryResult",
    "DataQualityReport", "DataQualityPolicy", "evaluate_data_quality",
    "ConfigValidationResult", "MLRuntimeConfig", "validate_ml_config",
    "DegradationDecision", "evaluate_degradation",
    "ARTIFACT_SCHEMA_VERSION", "IntegrityReport", "CompatibilityReport",
    "verify_artifact_integrity", "check_schema_compatibility", "load_with_integrity",
    "atomic_write_text", "atomic_write_bytes",
    "ArtifactManifest", "MANIFEST_VERSION", "build_manifest_from_bundle", "validate_manifest",
    "save_manifest", "load_manifest", "verify_manifest_against_disk", "feature_schema_hash",
    "SafeRollbackResult", "safe_rollback",
    "TransitionResult", "is_legal_transition", "validate_transition", "apply_transition", "LEGAL_TRANSITIONS",
    "FreshnessReport", "FreshnessPolicy", "evaluate_freshness",
]
