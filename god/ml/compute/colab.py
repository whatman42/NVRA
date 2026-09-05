"""Google Colab Free — opportunistic optional provider (lazy, never required).

Security contract:
- HEAVY training/research only
- No secrets, no broker credentials, no execution commands
- Output is untrusted; promotion requires local validation
- Disconnect / missing session => INTERRUPTED or UNKNOWN, never SUCCESS
"""
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


def _detect_colab_runtime() -> bool:
    """True only when actually running inside a Colab kernel."""
    try:
        import importlib.util

        return importlib.util.find_spec("google.colab") is not None
    except Exception:
        return False


class ColabComputeProvider(ComputeProvider):
    """Opportunistic Colab backend. Disconnect => INTERRUPTED, never SUCCESS."""

    name = "colab"

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
        if _detect_colab_runtime():
            return ProviderCapability(
                name=self.name,
                status=ProviderStatus.AVAILABLE,
                supports_training=True,
                supports_inference=False,
                notes=("colab_runtime", "opportunistic", "heavy_only"),
            )
        return ProviderCapability(
            name=self.name,
            status=ProviderStatus.UNAVAILABLE,
            supports_training=True,
            supports_inference=False,
            notes=("no_colab_runtime", "opportunistic"),
        )

    def submit(self, job: TrainingJob, payload: Optional[Mapping[str, Any]] = None) -> TrainingResult:
        # Sanitize first — never let secrets leave process.
        safe = sanitize_mapping(payload)
        try:
            assert_no_secrets(safe)
            assert_no_secrets(job.metadata)
            assert_no_execution_commands(safe)
            assert_no_execution_commands(job.metadata)
            # Also check original payload for execution commands (defense in depth).
            assert_no_execution_commands(payload)
        except ValueError as exc:
            job.status = JobStatus.REJECTED
            job.provider = self.name
            job.metadata = {**job.metadata, "reason": str(exc)}
            note = (
                "rejected_execution_command"
                if "execution" in str(exc).lower()
                else "rejected_secret"
            )
            return TrainingResult(job=job, provider_notes=(note,))

        job.provider = self.name

        # Reject non-heavy workloads on Colab path.
        if not job.is_heavy():
            job.status = JobStatus.REJECTED
            job.metadata = {
                **job.metadata,
                "reason": "colab_rejects_non_heavy_workload",
                "workload_type": job.workload_type,
            }
            return TrainingResult(job=job, provider_notes=("rejected_non_heavy",))

        cap = self.probe()
        if cap.status in (ProviderStatus.DISABLED, ProviderStatus.UNAVAILABLE, ProviderStatus.FAILED):
            job.status = JobStatus.FAILED
            job.metadata = {**job.metadata, "reason": f"provider_{cap.status.value.lower()}"}
            return TrainingResult(job=job, provider_notes=(cap.status.value,))

        if self._force_disconnect or cap.status == ProviderStatus.INTERRUPTED:
            job.status = JobStatus.INTERRUPTED
            job.metadata = {**job.metadata, "reason": "session_disconnected"}
            return TrainingResult(job=job, provider_notes=("interrupted", "not_success"))

        # Real Colab execution is out-of-process (notebook worker).
        # Without an authenticated external session, mark UNKNOWN — never SUCCESS.
        job.status = JobStatus.UNKNOWN
        job.metadata = {
            **job.metadata,
            "reason": "colab_requires_external_session",
            "payload_keys": sorted(safe.keys()),
            "tenant_id": job.tenant_id,
            "workload_type": job.workload_type,
        }
        if job.tenant_id:
            job.provenance = {
                **job.provenance,
                "tenant_id": job.tenant_id,
                "provider": self.name,
            }
        return TrainingResult(job=job, provider_notes=("external_session_required", "untrusted_output"))
