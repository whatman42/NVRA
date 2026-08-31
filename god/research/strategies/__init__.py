"""Phase 4C — Strategy Lifecycle & Evolution (research only).

Strategy = versioned research artifact.
ZERO capital authority. No real-money execution. No LIVE state.
"""

from .models import (
    ComparisonEvidence,
    LifecycleState,
    MutationRecord,
    MutationType,
    ResearchStrategy,
    TransitionRecord,
)
from .states import ALLOWED_TRANSITIONS, can_transition
from .lifecycle import LifecycleEngine
from .registry import StrategyRegistry
from .mutation import MutationEngine
from .evolution import EvolutionEngine
from .comparison import ComparisonEngine
from .degradation import DegradationService
from .retirement import RetirementService
from .lineage import ancestors, descendants, full_family_tree, parent_of

__all__ = [
    "ComparisonEvidence",
    "LifecycleState",
    "MutationRecord",
    "MutationType",
    "ResearchStrategy",
    "TransitionRecord",
    "ALLOWED_TRANSITIONS",
    "can_transition",
    "LifecycleEngine",
    "StrategyRegistry",
    "MutationEngine",
    "EvolutionEngine",
    "ComparisonEngine",
    "DegradationService",
    "RetirementService",
    "ancestors",
    "descendants",
    "full_family_tree",
    "parent_of",
]
