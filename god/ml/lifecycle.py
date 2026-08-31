"""Model lifecycle hardening — integrity, schema compatibility, atomic persist.

Fail-closed on corrupt/incompatible artifacts. Never auto-promotes. Never LIVE.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .persist import ArtifactBundle, validate_artifact_bundle, load_trained_model_safe
from god.persist.atomic import atomic_write_bytes

# Bump only on breaking artifact format changes
ARTIFACT_SCHEMA_VERSION = "1.0"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()




@dataclass
class IntegrityReport:
    ok: bool
    status: str  # ok | missing | corrupt | schema_mismatch | checksum_mismatch | incompatible
    reasons: list[str] = field(default_factory=list)
    schema_version: str = ""
    artifact_checksum: str = ""
    expected_checksum: str = ""
    model_id: str = ""
    model_version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reasons": list(self.reasons),
            "schema_version": self.schema_version,
            "artifact_checksum": self.artifact_checksum,
            "expected_checksum": self.expected_checksum,
            "model_id": self.model_id,
            "model_version": self.model_version,
        }


@dataclass
class CompatibilityReport:
    compatible: bool
    reasons: list[str] = field(default_factory=list)
    expected_features_version: str = ""
    actual_features_version: str = ""
    expected_schema: str = ""
    actual_schema: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "compatible": self.compatible,
            "reasons": list(self.reasons),
            "expected_features_version": self.expected_features_version,
            "actual_features_version": self.actual_features_version,
            "expected_schema": self.expected_schema,
            "actual_schema": self.actual_schema,
        }


def atomic_write_text(path: Path, content: str, encoding: str = "utf-8") -> None:
    """Write via temp file + os.replace for crash-safe persistence."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def verify_artifact_integrity(
    root: Path,
    model_id: str,
    model_version: str,
    *,
    expected_schema: str = ARTIFACT_SCHEMA_VERSION,
) -> IntegrityReport:
    """Verify on-disk artifact: bundle present, schema, checksum match."""
    root = Path(root)
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in model_id)
    safe_ver = "".join(c if c.isalnum() or c in "._-" else "_" for c in model_version)
    mdir = root / "artifacts" / f"{safe_id}@{safe_ver}"
    bundle_path = mdir / "bundle.json"

    if not bundle_path.is_file():
        return IntegrityReport(
            ok=False,
            status="missing",
            reasons=["bundle_missing"],
            model_id=model_id,
            model_version=model_version,
        )

    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return IntegrityReport(
            ok=False,
            status="corrupt",
            reasons=["bundle_json_corrupt"],
            model_id=model_id,
            model_version=model_version,
        )

    reasons: list[str] = []
    schema = str(data.get("schema_version", "") or data.get("metadata", {}).get("schema_version", ""))
    if schema and schema != expected_schema:
        reasons.append(f"schema_mismatch:{schema}!={expected_schema}")
        return IntegrityReport(
            ok=False,
            status="schema_mismatch",
            reasons=reasons,
            schema_version=schema,
            model_id=model_id,
            model_version=model_version,
        )

    art_file = str(data.get("artifact_file", "model.pkl"))
    art_path = mdir / art_file
    if not art_path.is_file():
        return IntegrityReport(
            ok=False,
            status="missing",
            reasons=["artifact_file_missing"],
            schema_version=schema or expected_schema,
            model_id=model_id,
            model_version=model_version,
        )

    actual_cs = file_sha256(art_path)
    expected_cs = str(data.get("artifact_checksum", "") or data.get("metadata", {}).get("artifact_checksum", ""))
    if expected_cs and actual_cs != expected_cs:
        return IntegrityReport(
            ok=False,
            status="checksum_mismatch",
            reasons=["artifact_checksum_mismatch"],
            schema_version=schema or expected_schema,
            artifact_checksum=actual_cs,
            expected_checksum=expected_cs,
            model_id=model_id,
            model_version=model_version,
        )

    try:
        bundle = ArtifactBundle.from_dict(data)
        ok, reason = validate_artifact_bundle(bundle)
        if not ok:
            return IntegrityReport(
                ok=False,
                status="corrupt",
                reasons=[f"bundle_invalid:{reason}"],
                schema_version=schema or expected_schema,
                artifact_checksum=actual_cs,
                model_id=model_id,
                model_version=model_version,
            )
    except Exception as e:
        return IntegrityReport(
            ok=False,
            status="corrupt",
            reasons=[f"bundle_parse:{type(e).__name__}"],
            model_id=model_id,
            model_version=model_version,
        )

    return IntegrityReport(
        ok=True,
        status="ok",
        schema_version=schema or expected_schema,
        artifact_checksum=actual_cs,
        expected_checksum=expected_cs or actual_cs,
        model_id=model_id,
        model_version=model_version,
    )


def check_schema_compatibility(
    bundle: ArtifactBundle,
    *,
    expected_features_version: str = "",
    expected_schema: str = ARTIFACT_SCHEMA_VERSION,
) -> CompatibilityReport:
    """Reject incompatible feature schema / artifact schema."""
    reasons: list[str] = []
    actual_schema = str(
        (bundle.metadata or {}).get("schema_version", "") or getattr(bundle, "schema_version", "") or ""
    )
    if actual_schema and actual_schema != expected_schema:
        reasons.append(f"schema_incompatible:{actual_schema}")
    if expected_features_version and bundle.features_version and bundle.features_version != expected_features_version:
        reasons.append(f"features_version_mismatch:{bundle.features_version}!={expected_features_version}")
    if not bundle.feature_names:
        reasons.append("empty_feature_names")
    return CompatibilityReport(
        compatible=len(reasons) == 0,
        reasons=reasons,
        expected_features_version=expected_features_version,
        actual_features_version=bundle.features_version,
        expected_schema=expected_schema,
        actual_schema=actual_schema or expected_schema,
    )


def load_with_integrity(
    root: Path,
    model_id: str,
    model_version: str,
    *,
    expected_features_version: str = "",
) -> tuple[Optional[Any], Optional[Any], Optional[ArtifactBundle], IntegrityReport]:
    """Load only if integrity + optional schema compatibility pass. Fail-closed."""
    irep = verify_artifact_integrity(root, model_id, model_version)
    if not irep.ok:
        return None, None, None, irep

    model, cal, bundle, status = load_trained_model_safe(root, model_id, model_version)
    if status != "ok" or model is None or bundle is None:
        return None, None, None, IntegrityReport(
            ok=False,
            status="corrupt" if status != "missing" else "missing",
            reasons=[f"safe_load:{status}"],
            model_id=model_id,
            model_version=model_version,
        )

    crep = check_schema_compatibility(
        bundle, expected_features_version=expected_features_version
    )
    if not crep.compatible:
        return None, None, None, IntegrityReport(
            ok=False,
            status="incompatible",
            reasons=crep.reasons,
            model_id=model_id,
            model_version=model_version,
            schema_version=crep.actual_schema,
        )

    return model, cal, bundle, irep
