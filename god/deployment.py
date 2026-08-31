"""Compatibility deployment facade for the legacy final-readiness gate.

This is deliberately paper/readiness-only.  Real broker deployment remains in
the existing ``god.bridge`` installer/healing path and is not duplicated here.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class DeploymentState(str, Enum):
    STOPPED = "STOPPED"
    RUNNING = "RUNNING"
    READY = "READY"
    FAILED = "FAILED"


@dataclass(frozen=True)
class DeploymentResult:
    state: DeploymentState
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"state": self.state.value, "detail": self.detail}


class ProductionDeploymentRunner:
    """Readiness-only lifecycle adapter; never submits broker orders."""

    def __init__(self, config: Any = None, *, observability: Any = None) -> None:
        self.config = config
        self.observability = observability
        self.state = DeploymentState.STOPPED

    def start(self) -> DeploymentResult:
        self.state = DeploymentState.RUNNING
        return DeploymentResult(self.state, "paper_readiness_runtime_started")

    def shutdown(self) -> DeploymentResult:
        self.state = DeploymentState.STOPPED
        return DeploymentResult(self.state, "paper_readiness_runtime_stopped")
