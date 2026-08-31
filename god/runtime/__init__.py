"""N.U.N.G. / NVRA runtime package.

Phase 4M: CognitiveRuntimeRunner
Phase 7B: brain entrypoint (main)
"""

from .clock import Clock, FixedClock, SystemClock
from .freshness import assess_freshness
from .models import (
    FreshnessPolicy,
    FreshnessStatus,
    RuntimeConfig,
    RuntimeHealth,
    RuntimeOutcome,
    RuntimeResult,
    RuntimeStatus,
)
from .runner import CognitiveRuntimeRunner
from .scheduler import Scheduler
from .main import BUILD_ID, PRODUCT_VERSION, main

__all__ = [
    "Clock",
    "FixedClock",
    "SystemClock",
    "assess_freshness",
    "FreshnessPolicy",
    "FreshnessStatus",
    "RuntimeConfig",
    "RuntimeHealth",
    "RuntimeOutcome",
    "RuntimeResult",
    "RuntimeStatus",
    "CognitiveRuntimeRunner",
    "Scheduler",
    "main",
    "PRODUCT_VERSION",
    "BUILD_ID",
]
