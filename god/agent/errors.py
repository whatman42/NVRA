"""Agent error hierarchy — no trading intelligence."""

from __future__ import annotations


class AgentError(Exception):
    """Base error for agent runtime."""


class InvalidStateError(AgentError):
    """Lifecycle transition not allowed from current state."""


class ExecutionError(AgentError):
    """ExecutionProvider failed to process a request."""


class IdempotencyError(AgentError):
    """Duplicate request_id detected; original result is returned instead of re-executing."""


class RecoveryError(AgentError):
    """Recovery / reconciliation after crash failed."""


class ObservationError(AgentError):
    """Observer could not produce a valid observation."""


class DecisionError(AgentError):
    """Decider could not produce a valid decision."""
