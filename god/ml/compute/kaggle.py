"""Kaggle Notebook — opportunistic optional provider (lazy, never required)."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .base import ComputeProvider
from .security import assert_no_execution_commands, assert_no_secrets, sanitize_mapping
from .types import (
    JobStatus,
    ProviderCapability,
    ProviderStatus,
    TrainingJob,
    TrainingResult,
)


def _detect_kaggle_runtime() -> bool:
    try:
        import os

        return bool(os.environ.get("KAGGLE_KERNEL_RUN_TYPE") or os.environ.get("KAGGLE_URL_BASE"))
    except Exception:
        return False


class KaggleComputeProvider(ComputeProvider):
    name = "kaggle"

    def __init__(self, *, enabled: bool = False, opportunistic: bool = True) -> None:
        self.enabled = bool(enabled)
        self.opportunistic = bool(opportunistic)
        self._force_status: Optional[ProviderStatus] = None
        self._force_disconnect: bool = False

    def probe(self) -> ProviderCapability:
        if self._force_status is not None:
            return ProviderCapability(
                name=self.name,
                status=self._force_status,
                supports_training=True,
                supports_inference=False,
                notes=("forced",),
            )
        if not self.enabled:
            return ProviderCapability(
                name=self.name,
                status=ProviderStatus.DISABLED,
                supports_training=True,
                supports_inference=False,
                notes=("disabled_by_config",),
            )
        if _detect_kaggle_runtime():
            return ProviderCapability(
                name=self.name,
                status=ProviderStatus.AVAILABLE,
                supports_training=True,
                supports_inference=False,
                notes=("kaggle_runtime", "opportunistic", "heavy_only"),
            )
        return ProviderCapability(
            name=self.name,
            status=ProviderStatus.UNAVAILABLE,
            supports_training=True,
            supports_inference=False,
            notes=("no_kaggle_runtime", "opportunistic"),
        )

    def submit(self, job: TrainingJob, payload: Optional[Mapping[str, Any]] = None) -> TrainingResult:
        safe = sanitize_mapping(payload)
        assert_no_secrets(safe)
        assert_no_secrets(job.metadata)
        assert_no_execution_commands(safe)
        assert_no_execution_commands(job.metadata)
        job.provider = self.name

        if not job.is_heavy():
            job.status = JobStatus.REJECTED
            job.metadata = {
                **job.metadata,
                "reason": "kaggle_rejects_non_heavy_workload",
                "workload_type": job.workload_type,
            }
            return TrainingResult(job=job, provider_notes=("rejected_non_heavy",))

        try:
            assert_no_execution_commands(payload)
        except ValueError as exc:
            job.status = JobStatus.REJECTED
            job.metadata = {**job.metadata, "reason": str(exc)}
            return TrainingResult(job=job, provider_notes=("rejected_execution_command",))

        cap = self.probe()
        if cap.status in (ProviderStatus.DISABLED, ProviderStatus.UNAVAILABLE, ProviderStatus.FAILED):
            job.status = JobStatus.FAILED
            job.metadata = {**job.metadata, "reason": f"provider_{cap.status.value.lower()}"}
            return TrainingResult(job=job, provider_notes=(cap.status.value,))

        if self._force_disconnect or cap.status == ProviderStatus.INTERRUPTED:
            job.status = JobStatus.INTERRUPTED
            job.metadata = {**job.metadata, "reason": "session_disconnected"}
            return TrainingResult(job=job, provider_notes=("interrupted", "not_success"))

        job.status = JobStatus.UNKNOWN
        job.metadata = {
            **job.metadata,
            "reason": "kaggle_requires_external_session",
            "payload_keys": sorted(safe.keys()),
            "tenant_id": job.tenant_id,
            "workload_type": job.workload_type,
        }
        return TrainingResult(job=job, provider_notes=("external_session_required", "untrusted_output"))
