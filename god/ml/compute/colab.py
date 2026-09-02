"""Google Colab Free — opportunistic optional provider (lazy, never required)."""
from __future__ import annotations

from typing import Any, Mapping, Optional

from .base import ComputeProvider
from .security import assert_no_secrets, sanitize_mapping
from .types import (
    JobStatus,
    ProviderCapability,
    ProviderStatus,
    TrainingJob,
    TrainingResult,
)


def _detect_colab_runtime() -> bool:
    """True only when actually running inside a Colab kernel. Never import at module load for side effects beyond probe."""
    try:
        import importlib.util

        # google.colab exists only inside Colab; absence is normal.
        return importlib.util.find_spec("google.colab") is not None
    except Exception:
        return False


class ColabComputeProvider(ComputeProvider):
    """Opportunistic Colab backend. Disconnect => INTERRUPTED, never SUCCESS."""

    name = "colab"

    def __init__(self, *, enabled: bool = False, opportunistic: bool = True) -> None:
        self.enabled = bool(enabled)
        self.opportunistic = bool(opportunistic)
        # Test double injection
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
                notes=("colab_runtime", "opportunistic"),
            )
        return ProviderCapability(
            name=self.name,
            status=ProviderStatus.UNAVAILABLE,
            supports_training=True,
            supports_inference=False,
            notes=("no_colab_runtime", "opportunistic"),
        )

    def submit(self, job: TrainingJob, payload: Optional[Mapping[str, Any]] = None) -> TrainingResult:
        safe = sanitize_mapping(payload)
        assert_no_secrets(safe)
        assert_no_secrets(job.metadata)
        job.provider = self.name

        cap = self.probe()
        if cap.status in (ProviderStatus.DISABLED, ProviderStatus.UNAVAILABLE, ProviderStatus.FAILED):
            job.status = JobStatus.FAILED
            job.metadata = {**job.metadata, "reason": f"provider_{cap.status.value.lower()}"}
            return TrainingResult(job=job, provider_notes=(cap.status.value,))

        if self._force_disconnect or cap.status == ProviderStatus.INTERRUPTED:
            job.status = JobStatus.INTERRUPTED
            job.metadata = {**job.metadata, "reason": "session_disconnected"}
            return TrainingResult(job=job, provider_notes=("interrupted", "not_success"))

        # Real Colab execution is out-of-process (notebook). In-process we only mark readiness.
        # Without an attached session worker, treat as UNKNOWN rather than SUCCESS.
        job.status = JobStatus.UNKNOWN
        job.metadata = {
            **job.metadata,
            "reason": "colab_requires_external_session",
            "payload_keys": sorted(safe.keys()),
        }
        return TrainingResult(job=job, provider_notes=("external_session_required",))
