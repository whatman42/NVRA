"""Governor state machine — computational load only."""

from __future__ import annotations

from enum import Enum, auto


class GovernorState(Enum):
    NORMAL = auto()
    DEGRADED = auto()
    CONSTRAINED = auto()
    CRITICAL = auto()
    RECOVERY = auto()


class RingStatus(Enum):
    PROTECTED = auto()  # Ring 0 always
    FULL = auto()
    REDUCED = auto()
    SUSPENDED = auto()


class MemoryPressure(Enum):
    NORMAL = auto()
    WARNING = auto()
    CRITICAL = auto()
    UNKNOWN = auto()


class DataFreshness(Enum):
    FRESH = auto()
    AGING = auto()
    STALE = auto()
    CRITICAL_STALE = auto()


# Degradation severity levels (0 = full, 6 = critical compute only)
DEGRADATION_LEVELS = {
    GovernorState.NORMAL: 0,
    GovernorState.DEGRADED: 2,
    GovernorState.CONSTRAINED: 4,
    GovernorState.CRITICAL: 6,
    GovernorState.RECOVERY: 3,  # intermediate ramp
}


def ring0_status(_state: GovernorState) -> RingStatus:
    return RingStatus.PROTECTED


def ring1_status(state: GovernorState) -> RingStatus:
    if state is GovernorState.NORMAL:
        return RingStatus.FULL
    if state in (GovernorState.DEGRADED, GovernorState.RECOVERY):
        return RingStatus.REDUCED
    if state is GovernorState.CONSTRAINED:
        return RingStatus.REDUCED
    return RingStatus.SUSPENDED  # CRITICAL — minimal


def ring2_status(state: GovernorState) -> RingStatus:
    if state is GovernorState.NORMAL:
        return RingStatus.FULL
    # DEGRADED and below: stop expendable work
    return RingStatus.SUSPENDED
