"""Component protocols for Agent Skeleton.

Each stage is independently testable.
No trading strategy is embedded in these contracts.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, Optional, Any

from .models import (
    RuntimeObservation,
    RuntimeDecision,
    ExecutionRequest,
    ExecutionResult,
    Measurement,
    LearningResult,
    LifecycleState,
)


@runtime_checkable
class Observer(Protocol):
    """Produces immutable observations — answers 'what is happening?'."""

    def observe(self) -> RuntimeObservation:
        ...


@runtime_checkable
class Decider(Protocol):
    """Produces typed decisions from an observation.

    Phase 3 implementations must NOT hard-code technical-indicator rules.
    """

    def decide(self, observation: RuntimeObservation) -> RuntimeDecision:
        ...


@runtime_checkable
class Executor(Protocol):
    """Submits decisions to an ExecutionProvider and returns results."""

    def execute(self, decision: RuntimeDecision) -> ExecutionResult:
        ...


@runtime_checkable
class Measurer(Protocol):
    """Compares intended decision vs actual execution outcome."""

    def measure(
        self,
        decision: RuntimeDecision,
        result: ExecutionResult,
        latency_ms: float = 0.0,
    ) -> Measurement:
        ...


@runtime_checkable
class Learner(Protocol):
    """LearningEngine interface only — no real model training in Phase 3."""

    def learn(
        self,
        observation: RuntimeObservation,
        decision: RuntimeDecision,
        result: ExecutionResult,
        measurement: Measurement,
    ) -> LearningResult:
        ...


@runtime_checkable
class LifecycleManager(Protocol):
    """Owns persistent lifecycle state transitions and recovery."""

    @property
    def state(self) -> LifecycleState:
        ...

    def transition(self, to: LifecycleState, reason: str = "") -> None:
        ...

    def recover(self) -> None:
        ...
