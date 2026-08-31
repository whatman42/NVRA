"""Phase 5A — N.U.N.G. Execution Contract & Null Execution.

ShadowDecision → ExecutionIntent → validate → NullExecutionProvider → ExecutionResult

SIMULATED only. executed=False. No broker. No MT5. No real orders.
"""

from .models import (
    ExecutionIntent,
    ExecutionResult,
    IntentAction,
    IntentStatus,
    ResultStatus,
)
from .validator import ExecutionValidator, validate_intent
from .null_provider import NullExecutionProvider
from .engine import ExecutionContractEngine
from .provider import ExecutionProvider

__all__ = [
    "ExecutionIntent",
    "ExecutionResult",
    "IntentAction",
    "IntentStatus",
    "ResultStatus",
    "ExecutionValidator",
    "validate_intent",
    "NullExecutionProvider",
    "ExecutionContractEngine",
    "ExecutionProvider",
]
