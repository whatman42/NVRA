"""Model artifact packaging with schema validation (untrusted input)."""

from __future__ import annotations

import hashlib
import json
import os
import time
import hmac
from pathlib import Path
from typing import Any

from crypto.ml.backends import load_model_bytes
from crypto.ml.base import BaseModel, ModelMetadata
from crypto.ml.features import FEATURE_SCHEMA_VERSION


class ArtifactError(ValueError):
    """Invalid or incompatible model artifact."""


def data_hash(rows: list[tuple[float, ...]]) -> str:
    h = hashlib.sha256()
    for row in rows:
        h.update(repr(row).encode("utf-8"))
    return h.hexdigest()[:16]


def save_artifact(
    path: str | Path,
    model: BaseModel,
    meta: ModelMetadata,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    blob = model.save_bytes()
    payload = {
        "meta": meta.to_dict(),
        "model_b64_len": len(blob),
    }
    # Store side-by-side: .json metadata + .bin model
    path.with_suffix(".json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    bin_path = path.with_suffix(".bin")
    bin_path.write_bytes(blob)
    try:
        os.chmod(bin_path, 0o600)
    except OSError:
        pass
    checksum = hashlib.sha256(blob).hexdigest()
    checksum_path = path.with_suffix(".sha256")
    checksum_path.write_text(checksum + "  " + bin_path.name + "\n", encoding="utf-8")
    try:
        os.chmod(checksum_path, 0o600)
    except OSError:
        pass


def load_artifact(
    path: str | Path,
    *,
    expected_schema: str = FEATURE_SCHEMA_VERSION,
) -> tuple[BaseModel, ModelMetadata]:
    path = Path(path)
    meta_path = path.with_suffix(".json")
    bin_path = path.with_suffix(".bin")
    if not meta_path.is_file() or not bin_path.is_file():
        raise ArtifactError(f"artifact incomplete: {path}")

    try:
        payload: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        meta = ModelMetadata.from_dict(payload["meta"])
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"corrupt metadata: {exc}") from exc

    # Security / compatibility checks
    if meta.feature_schema_version != expected_schema:
        raise ArtifactError(
            f"feature schema mismatch: artifact={meta.feature_schema_version} "
            f"expected={expected_schema}"
        )
    # Reject metadata that looks like it contains secrets
    blob_text = json.dumps(meta.to_dict()).lower()
    for bad in ("api_key", "api_secret", "password", "private_key"):
        if bad in blob_text:
            raise ArtifactError("artifact metadata contains forbidden secret-like fields")

    raw = bin_path.read_bytes()
    checksum_path = path.with_suffix(".sha256")
    if not checksum_path.is_file():
        raise ArtifactError("missing trusted artifact checksum")
    try:
        expected_checksum = checksum_path.read_text(encoding="utf-8").strip().split()[0]
    except (OSError, IndexError):
        raise ArtifactError("invalid artifact checksum")
    actual_checksum = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(actual_checksum, expected_checksum):
        raise ArtifactError("artifact_checksum_mismatch")
    try:
        model = load_model_bytes(meta.algorithm, raw, trusted=True)
    except Exception as exc:  # noqa: BLE001
        raise ArtifactError(f"failed to load model bytes: {exc}") from exc
    return model, meta


def new_metadata(
    *,
    algorithm: str,
    feature_names: tuple[str, ...],
    training_rows: int,
    training_data_hash: str,
    hyperparameters: dict[str, Any],
    metrics: dict[str, float],
    profile: str,
    horizon: int,
) -> ModelMetadata:
    return ModelMetadata(
        model_id=hashlib.sha256(
            f"{algorithm}:{training_data_hash}:{time.time()}".encode()
        ).hexdigest()[:12],
        version="1",
        algorithm=algorithm,
        feature_schema_version=FEATURE_SCHEMA_VERSION,
        feature_names=feature_names,
        training_rows=training_rows,
        training_data_hash=training_data_hash,
        hyperparameters=hyperparameters,
        metrics=metrics,
        created_at_ms=int(time.time() * 1000),
        profile=profile,
        label_horizon_bars=horizon,
    )
