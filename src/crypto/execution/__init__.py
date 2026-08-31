"""Execution engine and reconciliation (Phase 5).

Sole path: RiskDecision → ExecutionEngine → (PAPER | LIVE adapter).
"""

from crypto.execution.adversarial import (
    PROFILES,
    AdversarialPaperBroker,
    AdversarialSimulationProfile,
)
from crypto.execution.engine import ExecutionEngine, ExecutionError
from crypto.execution.models import (
    ExecutionMode,
    ExecutionRecord,
    Fill,
    make_client_order_id,
    make_execution_id,
)
from crypto.execution.paper import PaperBroker
from crypto.execution.states import OrderState, TransitionError, can_transition, transition
from crypto.execution.store import ExecutionStore

__all__ = [
    "AdversarialPaperBroker",
    "AdversarialSimulationProfile",
    "PROFILES",
    "ExecutionEngine",
    "ExecutionError",
    "ExecutionMode",
    "ExecutionRecord",
    "ExecutionStore",
    "Fill",
    "OrderState",
    "PaperBroker",
    "TransitionError",
    "can_transition",
    "transition",
    "make_client_order_id",
    "make_execution_id",
]
