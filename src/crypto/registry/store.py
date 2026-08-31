"""Local ModelRegistry with lifecycle, rollback, and canary support."""

from __future__ import annotations

import json
import time
from pathlib import Path

from crypto.ml.artifacts import ArtifactError, load_artifact
from crypto.ml.base import BaseModel, ModelMetadata
from crypto.ml.features import FEATURE_SCHEMA_VERSION
from crypto.registry.models import ModelStatus, RegistryEntry


class RegistryError(ValueError):
    """Registry operation failed."""


class ModelRegistry:
    """Filesystem-backed local registry. Never auto-trusts remote models."""

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._index_path = self._root / "index.json"
        self._entries: dict[str, RegistryEntry] = {}
        self._load_index()

    def _load_index(self) -> None:
        if not self._index_path.is_file():
            return
        data = json.loads(self._index_path.read_text(encoding="utf-8"))
        for item in data.get("entries", []):
            entry = RegistryEntry.from_dict(item)
            self._entries[entry.model_id] = entry

    def _save_index(self) -> None:
        payload = {
            "entries": [e.to_dict() for e in self._entries.values()],
            "updated_at_ms": int(time.time() * 1000),
        }
        self._index_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def register(
        self,
        meta: ModelMetadata,
        artifact_path: str,
        *,
        status: ModelStatus = ModelStatus.CANDIDATE,
    ) -> RegistryEntry:
        # Validate artifact before registering
        model, loaded_meta = load_artifact(artifact_path)
        if loaded_meta.model_id != meta.model_id:
            raise RegistryError("metadata model_id mismatch with artifact")
        if loaded_meta.feature_schema_version != FEATURE_SCHEMA_VERSION:
            raise RegistryError("incompatible feature schema")

        entry = RegistryEntry(
            model_id=meta.model_id,
            version=meta.version,
            algorithm=meta.algorithm,
            feature_schema_version=meta.feature_schema_version,
            feature_names=meta.feature_names,
            training_data_hash=meta.training_data_hash,
            metrics=dict(meta.metrics),
            status=status,
            artifact_path=str(artifact_path),
            created_at_ms=meta.created_at_ms or int(time.time() * 1000),
            training_rows=meta.training_rows,
            profile=meta.profile,
            label_horizon_bars=meta.label_horizon_bars,
            hyperparameters=dict(meta.hyperparameters),
        )
        self._entries[entry.model_id] = entry
        self._save_index()
        return entry

    def get(self, model_id: str) -> RegistryEntry | None:
        return self._entries.get(model_id)

    def list_entries(self, *, status: ModelStatus | None = None) -> list[RegistryEntry]:
        out = list(self._entries.values())
        if status is not None:
            out = [e for e in out if e.status is status]
        return sorted(out, key=lambda e: e.created_at_ms, reverse=True)

    def validate(self, model_id: str) -> RegistryEntry:
        entry = self._require(model_id)
        if entry.status is ModelStatus.INVALID:
            raise RegistryError("model already INVALID")
        # Re-check artifact
        try:
            load_artifact(entry.artifact_path)
        except ArtifactError as exc:
            entry.status = ModelStatus.INVALID
            entry.notes = str(exc)
            self._save_index()
            raise RegistryError(f"validation failed: {exc}") from exc
        entry.status = ModelStatus.VALIDATED
        self._save_index()
        return entry

    def activate(self, model_id: str) -> RegistryEntry:
        entry = self._require(model_id)
        if entry.status not in (
            ModelStatus.VALIDATED,
            ModelStatus.ACTIVE,
            ModelStatus.CANARY,
        ):
            raise RegistryError(f"cannot activate status={entry.status.name}; validate first")
        # Retire previous ACTIVE for same algorithm (keep one active per algo)
        for other in self._entries.values():
            if (
                other.algorithm == entry.algorithm
                and other.status is ModelStatus.ACTIVE
                and other.model_id != entry.model_id
            ):
                other.status = ModelStatus.RETIRED
        entry.status = ModelStatus.ACTIVE
        entry.activated_at_ms = int(time.time() * 1000)
        self._save_index()
        return entry

    def set_canary(self, model_id: str) -> RegistryEntry:
        entry = self._require(model_id)
        if entry.status not in (ModelStatus.VALIDATED, ModelStatus.CANARY):
            raise RegistryError("canary requires VALIDATED model")
        entry.status = ModelStatus.CANARY
        self._save_index()
        return entry

    def retire(self, model_id: str) -> RegistryEntry:
        entry = self._require(model_id)
        entry.status = ModelStatus.RETIRED
        self._save_index()
        return entry

    def mark_invalid(self, model_id: str, reason: str = "") -> RegistryEntry:
        entry = self._require(model_id)
        entry.status = ModelStatus.INVALID
        entry.notes = reason
        self._save_index()
        return entry

    def rollback(self, algorithm: str) -> RegistryEntry:
        """Restore most recent VALIDATED/RETIRED known-good for algorithm."""
        candidates = [
            e
            for e in self._entries.values()
            if e.algorithm == algorithm and e.status in (ModelStatus.VALIDATED, ModelStatus.RETIRED)
        ]
        if not candidates:
            raise RegistryError(f"no rollback candidate for {algorithm}")
        candidates.sort(key=lambda e: e.created_at_ms, reverse=True)
        # Demote current ACTIVE
        for e in self._entries.values():
            if e.algorithm == algorithm and e.status is ModelStatus.ACTIVE:
                e.status = ModelStatus.RETIRED
        chosen = candidates[0]
        chosen.status = ModelStatus.ACTIVE
        chosen.activated_at_ms = int(time.time() * 1000)
        self._save_index()
        return chosen

    def load_active_models(self) -> list[tuple[BaseModel, ModelMetadata]]:
        """Load ACTIVE models only (not CANARY, RETIRED, INVALID)."""
        result: list[tuple[BaseModel, ModelMetadata]] = []
        for entry in self.list_entries(status=ModelStatus.ACTIVE):
            try:
                model, meta = load_artifact(entry.artifact_path)
                result.append((model, meta))
            except ArtifactError:
                entry.status = ModelStatus.INVALID
        self._save_index()
        return result

    def load_canary_models(self) -> list[tuple[BaseModel, ModelMetadata]]:
        result: list[tuple[BaseModel, ModelMetadata]] = []
        for entry in self.list_entries(status=ModelStatus.CANARY):
            try:
                model, meta = load_artifact(entry.artifact_path)
                result.append((model, meta))
            except ArtifactError:
                entry.status = ModelStatus.INVALID
        self._save_index()
        return result

    def _require(self, model_id: str) -> RegistryEntry:
        entry = self._entries.get(model_id)
        if entry is None:
            raise RegistryError(f"unknown model_id={model_id}")
        return entry
