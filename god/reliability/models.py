"""Phase 6E — N.U.N.G. reliability models. Recovery ≠ Execution."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from god.research.provenance import content_hash


class FailureKind(str, Enum):
    TRANSIENT = "TRANSIENT"
    DEPENDENCY_FAILURE = "DEPENDENCY_FAILURE"
    DATA_FAILURE = "DATA_FAILURE"
    STATE_FAILURE = "STATE_FAILURE"
    CORRUPTION = "CORRUPTION"
    CONFIGURATION_FAILURE = "CONFIGURATION_FAILURE"
    SECURITY_FAILURE = "SECURITY_FAILURE"
    FATAL = "FATAL"
    UNKNOWN = "UNKNOWN"


class RecoveryState(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    FAILED = "FAILED"
    HALTED = "HALTED"


# Recoverable kinds
_RECOVERABLE = frozenset(
    {
        FailureKind.TRANSIENT,
        FailureKind.DEPENDENCY_FAILURE,
        FailureKind.DATA_FAILURE,
    }
)


def is_recoverable(kind: FailureKind) -> bool:
    return kind in _RECOVERABLE


SCHEMA_VERSION = "reliability-6e-v1"


@dataclass(frozen=True)
class FailureRecord:
    failure_id: str
    kind: FailureKind
    message: str
    content_hash: str
    schema_version: str = SCHEMA_VERSION
    component: str = ""
    cycle_id: str = ""
    recoverable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_id": self.failure_id,
            "kind": self.kind.value,
            "message": self.message,
            "component": self.component,
            "cycle_id": self.cycle_id,
            "recoverable": self.recoverable,
            "content_hash": self.content_hash,
            "schema_version": self.schema_version,
        }


def make_failure_id(payload: dict[str, Any]) -> str:
    return "fail-" + content_hash(payload)[:24]


def classify_exception(exc: BaseException) -> FailureKind:
    name = type(exc).__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timeout" in msg or "connection" in name:
        return FailureKind.TRANSIENT
    if "config" in msg:
        return FailureKind.CONFIGURATION_FAILURE
    if "corrupt" in msg or "hash" in msg:
        return FailureKind.CORRUPTION
    if "security" in msg or "unauthorized" in msg or "live" in msg:
        return FailureKind.SECURITY_FAILURE
    if "data" in msg or "stale" in msg:
        return FailureKind.DATA_FAILURE
    if "state" in msg:
        return FailureKind.STATE_FAILURE
    if "fatal" in msg:
        return FailureKind.FATAL
    return FailureKind.UNKNOWN
