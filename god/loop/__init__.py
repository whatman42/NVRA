"""Phase 4J — Autonomous Cognitive Loop Integration.

Binds 4H → 4I → 4D/4E/4F evidence fusion into one cycle.
Produces CognitiveAttentionSet — never orders.
"""

from .models import (
    AttentionItem,
    AttentionStatus,
    CognitiveAttentionSet,
    CycleResult,
    CycleStatus,
    EvidenceContext,
)
from .engine import CognitiveLoopEngine, LOOP_VERSION
from .evidence_fusion import fuse_evidence
from .reassessment import reassess_item, reassess_set
from .checkpoint import CycleCheckpointStore

__all__ = [
    "AttentionItem",
    "AttentionStatus",
    "CognitiveAttentionSet",
    "CycleResult",
    "CycleStatus",
    "EvidenceContext",
    "CognitiveLoopEngine",
    "LOOP_VERSION",
    "fuse_evidence",
    "reassess_item",
    "reassess_set",
    "CycleCheckpointStore",
]

# TAHAP 6 — control loop (extends; does not replace CognitiveLoopEngine)
from .control_states import ControlState, IllegalTransitionError, can_transition
from .control_cycle import ControlCycle, TransitionRecord
from .autonomous import AutonomousControlLoop, CycleOutcome

__all__ = list(__all__) + [
    "ControlState",
    "IllegalTransitionError",
    "can_transition",
    "ControlCycle",
    "TransitionRecord",
    "AutonomousControlLoop",
    "CycleOutcome",
]
