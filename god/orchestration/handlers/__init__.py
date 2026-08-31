"""Thin handlers over 4A–4F engines."""

from .curiosity import CuriosityHandler
from .research import ResearchHandler
from .strategy import StrategyHandler
from .reality_rca import RealityRCAHandler
from .drift_regime import DriftRegimeHandler
from .policy_capital import PolicyCapitalHandler
from .shadow import ShadowHandler, pure_shadow_metrics
from .cognitive_loop import CognitiveLoopHandler

__all__ = [
    "CuriosityHandler",
    "ResearchHandler",
    "StrategyHandler",
    "RealityRCAHandler",
    "DriftRegimeHandler",
    "PolicyCapitalHandler",
    "ShadowHandler",
    "pure_shadow_metrics",
    "CognitiveLoopHandler",
]
