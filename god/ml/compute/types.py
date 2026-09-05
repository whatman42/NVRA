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
    PREPARING = "PREPARING"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    COMPLETED = "COMPLETED"  # alias semantic for SUCCESS in external workers
    INTERRUPTED = "INTERRUPTED"
    UNKNOWN = "UNKNOWN"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    VALIDATED = "VALIDATED"


class WorkloadType(str, Enum):
    """Explicit workload class for provider policy.

    INFERENCE / LIGHT  → local only (trusted path)
    HEAVY              → eligible for Colab/Kaggle when enabled
    """

    INFERENCE = "inference"
    LIGHT = "light"
    HEAVY = "heavy"


@dataclass
class TrainingJob:
    """Portable training job — provider produces artifacts; NVRA governs promotion.

    Secrets must never appear in this contract. Tenant isolation is enforced by
    the caller and validated on promotion.
    """

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    tenant_id: str = ""
    model_id: str = ""
    model_version: str = "1"
    model_type: str = ""
    workload_type: str = WorkloadType.LIGHT.value
    dataset_id: str = ""
    dataset_hash: str = ""
    code_version: str = ""
    dependency_profile: str = "minimal"
    training_config_hash: str = ""
    provider: str = "local"
    requested_resources: dict[str, Any] = field(default_factory=dict)
    timeout_sec: int = 3600
    checkpoint_ref: str = ""
    artifact_ref: str = ""
    created_at: float = field(default_factory=time.time)
    status: JobStatus = JobStatus.PENDING
    metrics: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["status"] = self.status.value if isinstance(self.status, JobStatus) else str(self.status)
        return d

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TrainingJob":
        status = data.get("status", JobStatus.PENDING)
        if isinstance(status, str):
            try:
                status = JobStatus(status)
            except ValueError:
                status = JobStatus.UNKNOWN
        return cls(
            job_id=str(data.get("job_id") or uuid.uuid4().hex),
            tenant_id=str(data.get("tenant_id") or ""),
            model_id=str(data.get("model_id") or ""),
            model_version=str(data.get("model_version") or "1"),
            model_type=str(data.get("model_type") or ""),
            workload_type=str(data.get("workload_type") or WorkloadType.LIGHT.value),
            dataset_id=str(data.get("dataset_id") or ""),
            dataset_hash=str(data.get("dataset_hash") or ""),
            code_version=str(data.get("code_version") or ""),
            dependency_profile=str(data.get("dependency_profile") or "minimal"),
            training_config_hash=str(data.get("training_config_hash") or ""),
            provider=str(data.get("provider") or "local"),
            requested_resources=dict(data.get("requested_resources") or {}),
            timeout_sec=int(data.get("timeout_sec") or 3600),
            checkpoint_ref=str(data.get("checkpoint_ref") or ""),
            artifact_ref=str(data.get("artifact_ref") or ""),
            created_at=float(data.get("created_at") or time.time()),
            status=status,
            metrics=dict(data.get("metrics") or {}),
            metadata=dict(data.get("metadata") or {}),
            provenance=dict(data.get("provenance") or {}),
        )

    def is_heavy(self) -> bool:
        return str(self.workload_type).lower() in {
            WorkloadType.HEAVY.value,
            "heavy",
            "training_heavy",
            "neural",
            "ensemble_heavy",
            "hparam_search",
            "backtest_heavy",
        }


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
