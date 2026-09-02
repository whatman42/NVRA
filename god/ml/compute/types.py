"""Shared types for optional multi-provider compute."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Mapping, Optional
import time
import uuid


class ProviderStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"
    INTERRUPTED = "INTERRUPTED"
    FAILED = "FAILED"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    INTERRUPTED = "INTERRUPTED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


@dataclass
class TrainingJob:
    """Portable training job — provider produces artifacts; NVRA governs promotion."""

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    model_id: str = ""
    model_version: str = "1"
    dataset_id: str = ""
    dataset_hash: str = ""
    code_version: str = ""
    dependency_profile: str = "minimal"
    training_config_hash: str = ""
    provider: str = "local"
    checkpoint_ref: str = ""
    artifact_ref: str = ""
    created_at: float = field(default_factory=time.time)
    status: JobStatus = JobStatus.PENDING
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TrainingJob":
        status = data.get("status", JobStatus.PENDING)
        if isinstance(status, str):
            status = JobStatus(status)
        return cls(
            job_id=str(data.get("job_id") or uuid.uuid4().hex),
            model_id=str(data.get("model_id") or ""),
            model_version=str(data.get("model_version") or "1"),
            dataset_id=str(data.get("dataset_id") or ""),
            dataset_hash=str(data.get("dataset_hash") or ""),
            code_version=str(data.get("code_version") or ""),
            dependency_profile=str(data.get("dependency_profile") or "minimal"),
            training_config_hash=str(data.get("training_config_hash") or ""),
            provider=str(data.get("provider") or "local"),
            checkpoint_ref=str(data.get("checkpoint_ref") or ""),
            artifact_ref=str(data.get("artifact_ref") or ""),
            created_at=float(data.get("created_at") or time.time()),
            status=status,
            metrics=dict(data.get("metrics") or {}),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class ProviderCapability:
    name: str
    status: ProviderStatus
    supports_training: bool = True
    supports_inference: bool = False  # cloud must never own inference path
    notes: tuple[str, ...] = ()


@dataclass
class TrainingResult:
    job: TrainingJob
    artifact_hash: str = ""
    checkpoint_hash: str = ""
    provider_notes: tuple[str, ...] = ()
