"""Local CPU/GPU compute provider — always the safe baseline fallback."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Optional

from god.ml.hardware import ResourceGovernor, detect_hardware

from .base import ComputeProvider
from .security import assert_no_secrets, sanitize_mapping
from .types import (
    JobStatus,
    ProviderCapability,
    ProviderStatus,
    TrainingJob,
    TrainingResult,
)


class LocalComputeProvider(ComputeProvider):
    name = "local"

    def __init__(self, *, governor: Optional[ResourceGovernor] = None) -> None:
        self._governor = governor

    def probe(self) -> ProviderCapability:
        snap = detect_hardware()
        notes = list(snap.notes)
        if snap.gpu_available:
            notes.append(f"gpu:{snap.gpu_vendor or 'unknown'}")
        notes.append(f"ram_mb:{snap.total_ram_mb}")
        notes.append(f"threads:{snap.cpu_threads}")
        return ProviderCapability(
            name=self.name,
            status=ProviderStatus.AVAILABLE,
            supports_training=True,
            supports_inference=False,
            notes=tuple(notes),
        )

    def submit(self, job: TrainingJob, payload: Optional[Mapping[str, Any]] = None) -> TrainingResult:
        safe = sanitize_mapping(payload)
        assert_no_secrets(safe)
        assert_no_secrets(job.metadata)

        gov = self._governor or ResourceGovernor()
        if not gov.may_start_training():
            job.status = JobStatus.FAILED
            job.metadata = {**job.metadata, "reason": "resource_pressure_blocks_training"}
            return TrainingResult(job=job, provider_notes=("training_deferred",))

        # Local path: produce deterministic artifact metadata only (no cloud, no execution).
        # Real model fitting remains in god.ml.train / pipeline; this provider orchestrates jobs.
        job.status = JobStatus.RUNNING
        job.provider = self.name
        body = {
            "job_id": job.job_id,
            "model_id": job.model_id,
            "model_version": job.model_version,
            "dataset_hash": job.dataset_hash,
            "training_config_hash": job.training_config_hash,
            "payload": safe,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        artifact_hash = hashlib.sha256(raw).hexdigest()
        job.artifact_ref = f"local://{job.job_id}/{artifact_hash[:16]}"
        job.checkpoint_ref = f"local://{job.job_id}/ckpt"
        job.status = JobStatus.SUCCESS
        job.metrics = dict(job.metrics) or {"local_ok": 1.0}
        job.metadata = {**job.metadata, "artifact_hash": artifact_hash}
        return TrainingResult(
            job=job,
            artifact_hash=artifact_hash,
            checkpoint_hash=artifact_hash,
            provider_notes=("local_completed",),
        )
