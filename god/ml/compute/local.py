"""Local CPU/GPU compute provider — always the safe baseline fallback."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Optional

from god.ml.hardware import ResourceGovernor, detect_hardware

from .base import ComputeProvider
from .security import assert_no_execution_commands, assert_no_secrets, sanitize_mapping
from .types import (
    JobStatus,
    ProviderCapability,
    ProviderStatus,
    TrainingJob,
    TrainingResult,
)


class LocalComputeProvider(ComputeProvider):
    name = "local"

    def __init__(
        self,
        *,
        governor: Optional[ResourceGovernor] = None,
        artifact_dir: Optional[Path] = None,
    ) -> None:
        self._governor = governor
        self._artifact_dir = Path(artifact_dir) if artifact_dir else None

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
        assert_no_execution_commands(safe)
        assert_no_execution_commands(job.metadata)

        gov = self._governor or ResourceGovernor()
        if not gov.may_start_training():
            job.status = JobStatus.FAILED
            job.metadata = {**job.metadata, "reason": "resource_pressure_blocks_training"}
            return TrainingResult(job=job, provider_notes=("training_deferred",))

        job.status = JobStatus.RUNNING
        job.provider = self.name
        body = {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "model_id": job.model_id,
            "model_version": job.model_version,
            "workload_type": job.workload_type,
            "dataset_hash": job.dataset_hash,
            "training_config_hash": job.training_config_hash,
            "payload": safe,
        }
        raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        artifact_hash = hashlib.sha256(raw).hexdigest()

        artifact_path = ""
        if self._artifact_dir is not None:
            self._artifact_dir.mkdir(parents=True, exist_ok=True)
            out = self._artifact_dir / f"{job.job_id}.artifact"
            out.write_bytes(raw)
            artifact_path = str(out)
            job.artifact_ref = str(out)
        else:
            job.artifact_ref = f"local://{job.job_id}/{artifact_hash[:16]}"

        job.checkpoint_ref = f"local://{job.job_id}/ckpt"
        job.status = JobStatus.SUCCESS
        job.metrics = dict(job.metrics) or {"local_ok": 1.0}
        meta = {**job.metadata, "artifact_hash": artifact_hash}
        if artifact_path:
            meta["artifact_path"] = artifact_path
        if job.tenant_id:
            meta["tenant_id"] = job.tenant_id
            job.provenance = {**job.provenance, "tenant_id": job.tenant_id, "provider": self.name}
        job.metadata = meta
        return TrainingResult(
            job=job,
            artifact_hash=artifact_hash,
            checkpoint_hash=artifact_hash,
            provider_notes=("local_completed",),
        )
