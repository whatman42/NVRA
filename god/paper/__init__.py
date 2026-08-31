"""Phase 5B — N.U.N.G. Paper Execution Simulation Engine.

Simulation only. No broker. No MT5. No real orders. No capital allocation.
"""

from .models import PaperExecution, PaperFill, PaperStatus
from .state import PaperState
from .fill import simulate_fill, extract_reference_price
from .engine import PaperExecutionEngine
from .reconciliation import PaperReconciler, ReconciliationRecord, ReconciliationStatus, reconcile
from .consistency import consistency_check, verify_hash
from .recovery import PaperRecoveryService
from .portfolio import PaperPortfolioEngine, PaperPortfolioState, PortfolioStatus
from .performance import PaperPerformanceEngine, PerformanceMetrics, MetricsStatus
from .risk import PaperRiskEngine
from .risk_models import PaperRiskAssessment, RiskLevel, SafetyDecision, RiskStatus
from .safety import PaperSafetyGate
from .lifecycle import PaperLifecycleEngine, LifecycleState, LifecycleRecord, can_transition
from .orchestrator import PaperOrchestrator, PaperPipelineResult, PipelineStatus
from .pipeline import run_paper_cycle
from .readiness import PaperReadinessGate, ReadinessReport, ReadinessStatus, ReadinessCheck

__all__ = [
    "PaperExecution",
    "PaperFill",
    "PaperStatus",
    "PaperState",
    "simulate_fill",
    "extract_reference_price",
    "PaperExecutionEngine",
    "PaperReconciler",
    "ReconciliationRecord",
    "ReconciliationStatus",
    "reconcile",
    "consistency_check",
    "verify_hash",
    "PaperRecoveryService",
    "PaperPortfolioEngine",
    "PaperPortfolioState",
    "PortfolioStatus",
    "PaperPerformanceEngine",
    "PerformanceMetrics",
    "MetricsStatus",
    "PaperRiskEngine",
    "PaperRiskAssessment",
    "RiskLevel",
    "SafetyDecision",
    "RiskStatus",
    "PaperSafetyGate",
    "PaperLifecycleEngine",
    "LifecycleState",
    "LifecycleRecord",
    "can_transition",
    "PaperOrchestrator",
    "PaperPipelineResult",
    "PipelineStatus",
    "run_paper_cycle",
    "PaperReadinessGate",
    "ReadinessReport",
    "ReadinessStatus",
    "ReadinessCheck",
]
