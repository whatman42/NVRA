"""Phase 4A — Research & Evidence Engine (additive).

No live trading intelligence. No hard-coded strategy rules.
Parameters such as indicator names or risk ratios may appear only as
*candidate hypotheses* subject to experiment — never as system law.

Pipeline:
  DISCOVERY → DATA → RESEARCH → EVIDENCE → CLAIM → HYPOTHESIS
  → EXPERIMENT → VALIDATION → EXPERIENCE → LEARNING

Execution remains Virtual/Null until Phase 3B-D is verified on real Windows.

The public surface is kept compatible while heavy research modules are loaded
only when an exported attribute is accessed. This prevents package-level eager
imports from creating cross-domain initialization cycles.
"""

from importlib import import_module
from typing import Any

__all__ = [
    "ResearchEngine", "ExperimentRegistry", "assess_evidence", "AnomalyDetector", "AnomalyReport",
    "SourceTracker", "content_hash", "build_provenance", "AssessmentResult", "ClaimStatus",
    "EvidenceRecord", "ExperimentOutcome", "ExperimentStatus", "FactRecord", "HypothesisStatus",
    "ProvenanceRecord", "ResearchEvent", "SourceProfile", "SourceReliability", "CuriosityEngine",
    "CuriosityEvent", "ResearchTrigger", "ExperimentEngine", "ExperimentOutcomeExt", "ValidationMetadata",
    "record_validation", "Fold", "PBOResult", "combinatorial_purged_splits", "number_of_paths",
    "probability_of_backtest_overfitting", "deflated_sharpe_ratio", "ComparisonEngine", "ComparisonEvidence",
    "DegradationService", "EvolutionEngine", "LifecycleEngine", "LifecycleState", "MutationEngine",
    "MutationRecord", "MutationType", "ResearchStrategy", "RetirementService", "StrategyRegistry",
    "TransitionRecord", "AttributionStatus", "ComparisonStatus", "GapDimension", "MetricObservation",
    "RealityGap", "RealityGapEngine", "compare_metrics", "CausalStatus", "CauseCategory", "CauseHypothesis",
    "CauseRole", "FailureEvent", "FailureSeverity", "FailureStatus", "RCAEngine", "RootCauseAssessment",
    "DataQualityStatus", "DriftAssessment", "DriftCategory", "DriftEngine", "EpistemicState",
    "ObservationSeries", "EvidenceQuality", "RegimeAssessment", "RegimeEngine", "RegimeLabel",
    "RegimeTransition", "UncertaintyLevel",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "ResearchEngine": ("god.research.engine", "ResearchEngine"),
    "ExperimentRegistry": ("god.research.registry", "ExperimentRegistry"),
    "assess_evidence": ("god.research.assessment", "assess_evidence"),
    "AnomalyDetector": ("god.research.anomaly", "AnomalyDetector"),
    "AnomalyReport": ("god.research.anomaly", "AnomalyReport"),
    "SourceTracker": ("god.research.sources", "SourceTracker"),
    "content_hash": ("god.research.provenance", "content_hash"),
    "build_provenance": ("god.research.provenance", "build_provenance"),
    "AssessmentResult": ("god.research.models", "AssessmentResult"),
    "ClaimStatus": ("god.research.models", "ClaimStatus"),
    "EvidenceRecord": ("god.research.models", "EvidenceRecord"),
    "ExperimentOutcome": ("god.research.models", "ExperimentOutcome"),
    "ExperimentStatus": ("god.research.models", "ExperimentStatus"),
    "FactRecord": ("god.research.models", "FactRecord"),
    "HypothesisStatus": ("god.research.models", "HypothesisStatus"),
    "ProvenanceRecord": ("god.research.models", "ProvenanceRecord"),
    "ResearchEvent": ("god.research.models", "ResearchEvent"),
    "SourceProfile": ("god.research.models", "SourceProfile"),
    "SourceReliability": ("god.research.models", "SourceReliability"),
    "CuriosityEngine": ("god.research.curiosity", "CuriosityEngine"),
    "CuriosityEvent": ("god.research.curiosity", "CuriosityEvent"),
    "ResearchTrigger": ("god.research.curiosity", "ResearchTrigger"),
    "ExperimentEngine": ("god.research.experiments", "ExperimentEngine"),
    "ExperimentOutcomeExt": ("god.research.experiments", "ExperimentOutcomeExt"),
    "ValidationMetadata": ("god.research.validation", "ValidationMetadata"),
    "record_validation": ("god.research.validation", "record_validation"),
    "Fold": ("god.research.validation", "Fold"), "PBOResult": ("god.research.validation", "PBOResult"),
    "combinatorial_purged_splits": ("god.research.validation", "combinatorial_purged_splits"),
    "number_of_paths": ("god.research.validation", "number_of_paths"),
    "probability_of_backtest_overfitting": ("god.research.validation", "probability_of_backtest_overfitting"),
    "deflated_sharpe_ratio": ("god.research.validation", "deflated_sharpe_ratio"),
    "ComparisonEngine": ("god.research.strategies", "ComparisonEngine"),
    "ComparisonEvidence": ("god.research.strategies", "ComparisonEvidence"),
    "DegradationService": ("god.research.strategies", "DegradationService"),
    "EvolutionEngine": ("god.research.strategies", "EvolutionEngine"),
    "LifecycleEngine": ("god.research.strategies", "LifecycleEngine"),
    "LifecycleState": ("god.research.strategies", "LifecycleState"),
    "MutationEngine": ("god.research.strategies", "MutationEngine"),
    "MutationRecord": ("god.research.strategies", "MutationRecord"),
    "MutationType": ("god.research.strategies", "MutationType"),
    "ResearchStrategy": ("god.research.strategies", "ResearchStrategy"),
    "RetirementService": ("god.research.strategies", "RetirementService"),
    "StrategyRegistry": ("god.research.strategies", "StrategyRegistry"),
    "TransitionRecord": ("god.research.strategies", "TransitionRecord"),
    "AttributionStatus": ("god.research.reality", "AttributionStatus"),
    "ComparisonStatus": ("god.research.reality", "ComparisonStatus"),
    "GapDimension": ("god.research.reality", "GapDimension"),
    "MetricObservation": ("god.research.reality", "MetricObservation"),
    "RealityGap": ("god.research.reality", "RealityGap"),
    "RealityGapEngine": ("god.research.reality", "RealityGapEngine"),
    "compare_metrics": ("god.research.reality", "compare_metrics"),
    "CausalStatus": ("god.research.rca", "CausalStatus"),
    "CauseCategory": ("god.research.rca", "CauseCategory"),
    "CauseHypothesis": ("god.research.rca", "CauseHypothesis"),
    "CauseRole": ("god.research.rca", "CauseRole"),
    "FailureEvent": ("god.research.rca", "FailureEvent"),
    "FailureSeverity": ("god.research.rca", "FailureSeverity"),
    "FailureStatus": ("god.research.rca", "FailureStatus"),
    "RCAEngine": ("god.research.rca", "RCAEngine"),
    "RootCauseAssessment": ("god.research.rca", "RootCauseAssessment"),
    "DataQualityStatus": ("god.research.drift", "DataQualityStatus"),
    "DriftAssessment": ("god.research.drift", "DriftAssessment"),
    "DriftCategory": ("god.research.drift", "DriftCategory"),
    "DriftEngine": ("god.research.drift", "DriftEngine"),
    "EpistemicState": ("god.research.drift", "EpistemicState"),
    "ObservationSeries": ("god.research.drift", "ObservationSeries"),
    "EvidenceQuality": ("god.research.regime", "EvidenceQuality"),
    "RegimeAssessment": ("god.research.regime", "RegimeAssessment"),
    "RegimeEngine": ("god.research.regime", "RegimeEngine"),
    "RegimeLabel": ("god.research.regime", "RegimeLabel"),
    "RegimeTransition": ("god.research.regime", "RegimeTransition"),
    "UncertaintyLevel": ("god.research.regime", "UncertaintyLevel"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value
