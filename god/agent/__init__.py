"""Agent public API with lazy core imports to avoid execution/agent cycles."""
from .models import (LifecycleState, ActionType, AccountState, MarketState, RuntimeObservation, RuntimeDecision, ExecutionRequest, ExecutionResult, Measurement, LearningResult)
from .errors import (AgentError, InvalidStateError, ExecutionError, IdempotencyError, RecoveryError, ObservationError, DecisionError)
from .lifecycle import DefaultLifecycleManager

__all__ = [
    'LifecycleState','ActionType','AccountState','MarketState','RuntimeObservation','RuntimeDecision',
    'ExecutionRequest','ExecutionResult','Measurement','LearningResult','AgentError','InvalidStateError',
    'ExecutionError','IdempotencyError','RecoveryError','ObservationError','DecisionError',
    'DefaultLifecycleManager','AgentCore','DefaultObserver','StubDecider','DefaultExecutor','DefaultMeasurer','StubLearner'
]

def __getattr__(name):
    if name in {'AgentCore','DefaultObserver','StubDecider','DefaultExecutor','DefaultMeasurer','StubLearner'}:
        from .core import AgentCore, DefaultObserver, StubDecider, DefaultExecutor, DefaultMeasurer, StubLearner
        return locals()[name]
    raise AttributeError(name)
