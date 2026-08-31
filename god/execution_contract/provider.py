"""Execution provider protocol for N.U.N.G. Phase 5A — abstract only."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import ExecutionIntent, ExecutionResult


@runtime_checkable
class ExecutionProvider(Protocol):
    """Abstract provider. Implementations must not contact brokers in Phase 5A."""

    provider_id: str

    def execute(self, intent: ExecutionIntent) -> ExecutionResult: ...
