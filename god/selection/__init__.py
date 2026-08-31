"""Phase 4I — Autonomous Opportunity Selection.

Selects candidate × strategy combinations for cognitive attention.
Does NOT execute trades. Does NOT require daily manual pair/strategy selection.
"""

from .models import (
    Compatibility,
    Opportunity,
    OpportunitySelectionResult,
    SelectionResultStatus,
    SelectionStatus,
    UncertaintyLevel,
)
from .engine import SelectionEngine, SELECTION_VERSION
from .ranking import rank_opportunities
from .compatibility import evaluate_compatibility

__all__ = [
    "Compatibility",
    "Opportunity",
    "OpportunitySelectionResult",
    "SelectionResultStatus",
    "SelectionStatus",
    "UncertaintyLevel",
    "SelectionEngine",
    "SELECTION_VERSION",
    "rank_opportunities",
    "evaluate_compatibility",
]
