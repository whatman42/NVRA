"""Phase 6E — N.U.N.G. Production Reliability & Self-Recovery.

RECOVERY ≠ EXECUTION · RESTART ≠ AUTHORIZATION · READY ≠ LIVE · ALLOW ≠ OPEN
"""

from .models import (
    FailureKind,
    FailureRecord,
    RecoveryState,
    classify_exception,
    is_recoverable,
)
from .backoff import BackoffPolicy
from .supervisor import ReliabilitySupervisor

__all__ = [
    "FailureKind",
    "FailureRecord",
    "RecoveryState",
    "classify_exception",
    "is_recoverable",
    "BackoffPolicy",
    "ReliabilitySupervisor",
]
