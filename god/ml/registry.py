"""Model registry — promote only after validation; never auto-LIVE.

Persists champion artifact so reload after restart yields consistent predictions.
Stores optional hardware_profile / model_family without breaking older records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .calibration import PlattCalibrator, CalibrationResult
from .persist import ArtifactBundle, load_trained_model, save_trained_model
from .train import TrainedModel


@dataclass
class ModelRecord:
    model_id: str
    model_version: str
    status: str  # candidate | champion | retired | pruned
    features_version: str
    dataset_hash: str
    metrics: dict[str, float] = field(default_factory=dict)
    backend: str = ""
    path: str = ""
    saved_at: str = ""
    calibration_status: str = ""
    model_family: str = ""
    hardware_profile: str = ""
    oos_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_version": self.model_version,
            "status": self.status,
            "features_version": self.features_version,
            "dataset_hash": self.dataset_hash,
            "metrics": dict(self.metrics),
            "backend": self.backend,
            "path": self.path,
            "saved_at": self.saved_at,
            "calibration_status": self.calibration_status,
            "model_family": self.model_family,
            "hardware_profile": self.hardware_profile,
            "oos_metrics": dict(self.oos_metrics),
        }


class ModelRegistry:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "registry.json"
        self._records: list[ModelRecord] = []
        self._load()

    def _load(self) -> None:
        if self._index_path.is_file():
            data = json.loads(self._index_path.read_text(encoding="utf-8"))
            self._records = []
            for r in data.get("models", []):
                self._records.append(
                    ModelRecord(
                        model_id=r["model_id"],
                        model_version=r["model_version"],
                        status=r.get("status", "candidate"),
                        features_version=r.get("features_version", ""),
                        dataset_hash=r.get("dataset_hash", ""),
                        metrics=dict(r.get("metrics") or {}),
                        backend=r.get("backend", ""),
                        path=r.get("path", ""),
                        saved_at=r.get("saved_at", ""),
                        calibration_status=r.get("calibration_status", ""),
                        model_family=r.get("model_family", ""),
                        hardware_profile=r.get("hardware_profile", ""),
                        oos_metrics=dict(r.get("oos_metrics") or {}),
                    )
                )

    def _save(self) -> None:
        payload = {"models": [r.to_dict() for r in self._records]}
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def register_candidate(
        self,
        model: TrainedModel,
        *,
        calibrator: Optional[PlattCalibrator] = None,
        calibration: Optional[CalibrationResult] = None,
        metrics: Optional[dict[str, float]] = None,
        oos_metrics: Optional[dict[str, float]] = None,
        hardware_profile: str = "",
        model_family: str = "",
        persist: bool = True,
    ) -> ModelRecord:
        path = ""
        saved_at = ""
        cal_status = ""
        if persist:
            bundle = save_trained_model(
                self.root,
                model,
                calibrator=calibrator,
                calibration=calibration,
                extra_metrics=metrics,
            )
            path = f"artifacts/{model.model_id}@{model.model_version}"
            saved_at = bundle.saved_at
            if bundle.calibration:
                cal_status = str(bundle.calibration.get("status", ""))
        meta = model.metadata or {}
        hw = hardware_profile or str(meta.get("hardware_profile", ""))
        fam = model_family or str(meta.get("model_family", model.model_id))
        rec = ModelRecord(
            model_id=model.model_id,
            model_version=model.model_version,
            status="candidate",
            features_version=model.features_version,
            dataset_hash=model.dataset_hash,
            metrics={**model.metrics, **(metrics or {})},
            backend=model.backend,
            path=path,
            saved_at=saved_at,
            calibration_status=cal_status,
            model_family=fam,
            hardware_profile=hw,
            oos_metrics=dict(oos_metrics or {}),
        )
        self._records.append(rec)
        self._save()
        return rec

    def promote_champion(
        self,
        model_id: str,
        model_version: str,
        *,
        training_result: object | None = None,
        expected_dataset_hash: str = "",
        artifact_path: str | None = None,
        require_compute_gate: bool = False,
    ) -> ModelRecord:
        """Promote model to champion.

        When *training_result* is provided or *require_compute_gate* is True,
        compute artifact validation is mandatory (cannot be bypassed).
        Existing ML governance (evaluate_promotion / OOS gates) remains a
        separate caller responsibility; this is an additional integrity gate.
        """
        if training_result is not None or require_compute_gate:
            if training_result is None:
                raise PermissionError("compute_gate_required:training_result_missing")
            from god.ml.compute.validation import validate_training_result

            job = getattr(training_result, "job", None)
            exp = expected_dataset_hash
            if not exp and job is not None:
                exp = str(getattr(job, "dataset_hash", "") or "")
            # Fail-closed: compute-origin promotion always requires dataset provenance
            if not exp:
                raise PermissionError(
                    "compute_validation_rejected:missing_expected_dataset_hash"
                )
            gate = validate_training_result(
                training_result,  # type: ignore[arg-type]
                expected_dataset_hash=exp,
                artifact_path=artifact_path,
                require_resolvable_artifact=True,
            )
            if not gate.eligible_for_promotion:
                raise PermissionError(
                    "compute_validation_rejected:" + ",".join(gate.reasons)
                )

        found = None
        for r in self._records:
            if r.model_id == model_id and r.model_version == model_version:
                found = r
            elif r.status == "champion":
                r.status = "retired"
        if found is None:
            raise KeyError(f"model not found: {model_id}@{model_version}")
        found.status = "champion"
        self._save()
        return found

    def promote_from_compute(
        self,
        training_result: object,
        *,
        model_id: str = "",
        model_version: str = "",
        expected_dataset_hash: str = "",
        artifact_path: str | None = None,
    ) -> ModelRecord:
        """Mandatory compute-gated promotion — validation cannot be bypassed."""
        job = getattr(training_result, "job", None)
        mid = model_id or (getattr(job, "model_id", "") if job else "")
        mver = model_version or (getattr(job, "model_version", "1") if job else "1")
        if not mid:
            raise ValueError("model_id required for compute promotion")
        return self.promote_champion(
            mid,
            mver,
            training_result=training_result,
            expected_dataset_hash=expected_dataset_hash,
            artifact_path=artifact_path,
            require_compute_gate=True,
        )

    def champion(self) -> Optional[ModelRecord]:
        for r in self._records:
            if r.status == "champion":
                return r
        return None

    def load_champion(self) -> Optional[tuple[TrainedModel, Optional[PlattCalibrator], ArtifactBundle]]:
        rec = self.champion()
        if rec is None:
            return None
        try:
            return load_trained_model(self.root, rec.model_id, rec.model_version)
        except FileNotFoundError:
            return None

    def previous_champion(self) -> Optional[ModelRecord]:
        """Most recent retired/rolled_back model — candidate for rollback restore."""
        retired = [r for r in self._records if r.status in ("retired", "rolled_back")]
        if not retired:
            return None
        return sorted(retired, key=lambda r: r.saved_at or "", reverse=True)[0]

    def list_models(self) -> list[ModelRecord]:
        return list(self._records)
