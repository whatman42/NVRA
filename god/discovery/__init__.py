"""Phase 4H — Autonomous Market Discovery.

Discovers and ranks candidates over a configured universe.
Does NOT execute, allocate capital, or require daily manual pair/strategy selection.
NO_VALID_CANDIDATE is a valid successful outcome.
"""

from .models import (
    Candidate,
    DiscoveryResult,
    DiscoveryStatus,
    EligibilityStatus,
    InstrumentRef,
    InstrumentStatus,
    QualityStatus,
)
from .universe import Universe
from .data_quality import assess_observation_series
from .candidate import build_candidate
from .ranking import rank_candidates
from .scanner import Scanner
from .engine import DiscoveryEngine, DISCOVERY_VERSION

__all__ = [
    "Candidate",
    "DiscoveryResult",
    "DiscoveryStatus",
    "EligibilityStatus",
    "InstrumentRef",
    "InstrumentStatus",
    "QualityStatus",
    "Universe",
    "assess_observation_series",
    "build_candidate",
    "rank_candidates",
    "Scanner",
    "DiscoveryEngine",
    "DISCOVERY_VERSION",
]
