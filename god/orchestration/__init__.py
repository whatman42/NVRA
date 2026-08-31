"""Phase 4G — Cognitive Orchestrator (event-driven nervous system).

Coordinates 4A–4F. NEVER acquires execution authority.
ALLOW ≠ OPEN. Shadow ≠ real broker.
"""

from .models import (
    Checkpoint,
    CognitiveContext,
    CognitiveEvent,
    CognitiveStage,
    ContextStatus,
    EventType,
    FailureClass,
    MarketPhase,
    OrchTask,
    ResourceClass,
    SchedulerDecision,
    create_context,
    create_event,
    create_task,
    make_checkpoint,
    verify_checkpoint,
)
from .bus import EventBus
from .scheduler import Scheduler
from .checkpoint_store import CheckpointStore
from .context_store import ContextStore
from .worker import Worker
from .recovery import RecoveryService
from .handlers import (
    CuriosityHandler,
    ResearchHandler,
    StrategyHandler,
    RealityRCAHandler,
    DriftRegimeHandler,
    PolicyCapitalHandler,
    ShadowHandler,
)

__all__ = [
    "Checkpoint",
    "CognitiveContext",
    "CognitiveEvent",
    "CognitiveStage",
    "ContextStatus",
    "EventType",
    "FailureClass",
    "MarketPhase",
    "OrchTask",
    "ResourceClass",
    "SchedulerDecision",
    "create_context",
    "create_event",
    "create_task",
    "make_checkpoint",
    "verify_checkpoint",
    "EventBus",
    "Scheduler",
    "CheckpointStore",
    "ContextStore",
    "Worker",
    "RecoveryService",
    "CuriosityHandler",
    "ResearchHandler",
    "StrategyHandler",
    "RealityRCAHandler",
    "DriftRegimeHandler",
    "PolicyCapitalHandler",
    "ShadowHandler",
]
