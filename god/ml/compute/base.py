"""ComputeProvider abstraction — training/research only; never execution authority."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional

from .types import ProviderCapability, ProviderStatus, TrainingJob, TrainingResult


class ComputeProvider(ABC):
    """Backend for heavy training / analysis. Not part of signal/risk/execution path."""

    name: str = "base"

    @abstractmethod
    def probe(self) -> ProviderCapability:
        """Best-effort availability probe. Never raises for missing optional deps."""

    @abstractmethod
    def submit(self, job: TrainingJob, payload: Optional[Mapping[str, Any]] = None) -> TrainingResult:
        """Run or schedule a training job. Must not report SUCCESS on disconnect."""

    def is_available(self) -> bool:
        return self.probe().status == ProviderStatus.AVAILABLE
