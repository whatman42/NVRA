"""Portable NVRA state/model migration bundles.

A migration bundle is the supported way to move an installation to a new PC
without retraining from zero. It contains only explicitly allow-listed state,
model artifacts and non-secret configuration. Every payload file is checksummed.
Secrets, credentials and caches containing provider tokens are never exported.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 2
FORMAT = "nvra-migration-bundle"
DEFAULT_INCLUDE = (
    "state",
    "models",
    "ml",
    "artifacts",
    "data",
)
DENY_NAMES = {
    ".env", ".env.local", ".env.production", "credentials.json", "secrets.json",
    "api_keys.json", "private_key.pem", "id_rsa", "token.json",
}
DENY_SUFFIXES = (".pem", ".key", ".p12", ".pfx")


class MigrationError(Exception):
    """Raised when a migration bundle is invalid or unsafe to load."""


from god.persist.hash import sha256_file as _sha256


def _safe_relative(root: Path, path: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel.startswith("../") or rel == "..":
        raise MigrationError("path_escape")
    return rel


def _allowed(rel: str) -> bool:
    parts = Path(rel).parts
    if any(p in {".git", "__pycache__", ".pytest_cache"} for p in parts):
        return False
    name = parts[-1].lower()
    if name in DENY_NAMES:
        return False
    return not name.endswith(DENY_SUFFIXES)


@dataclass(frozen=True)
class MigrationManifest:
    schema_version: int
    format: str
    created_at: str
    files: dict[str, str]
    source_version: str = ""

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "format": self.format,
            "created_at": self.created_at,
            "source_version": self.source_version,
            "files": dict(sorted(self.files.items())),
        }


def _iter_payload_files(root: Path, include: Iterable[str]) -> list[Path]:
    found: list[Path] = []
    for item in include:
        base = (root / item).resolve()
        try:
            base.relative_to(root.resolve())
        except ValueError as exc:
            raise MigrationError(f"include_path_escape:{item}") from exc
        if not base.exists():
            continue
        if base.is_file():
            candidates = [base]
        else:
            candidates = [p for p in base.rglob("*") if p.is_file()]
        for path in candidates:
            rel = _safe_relative(root, path)
            if _allowed(rel):
                found.append(path)
    return sorted(set(found))


def create_migration_bundle(
    destination: str | Path,
    *,
    data_root: str | Path,
    include: Iterable[str] = DEFAULT_INCLUDE,
    extra_paths: dict[str, str | Path] | None = None,
    source_version: str = "",
) -> MigrationManifest:
    """Create a portable, checksummed ZIP from runtime/model state.

    The archive is deliberately allow-listed. It never recursively copies the
    whole home directory, which prevents accidental credential export.
    """
    destination = Path(destination)
    root = Path(data_root).expanduser().resolve()
    if not root.exists():
        raise MigrationError("data_root_not_found")
    files = _iter_payload_files(root, include)
    if not files and not extra_paths:
        raise MigrationError("no_migratable_state_found")

    staged_sources: list[tuple[str, Path]] = [(_safe_relative(root, p), p) for p in files]
    for archive_rel, raw_path in (extra_paths or {}).items():
        src = Path(raw_path).expanduser().resolve()
        if not src.exists() or not src.is_file():
            continue
        rel = archive_rel.strip("/").replace("\\", "/")
        if not rel or rel.startswith("../") or ".." in Path(rel).parts:
            raise MigrationError(f"unsafe_extra_path:{archive_rel}")
        if _allowed(rel):
            staged_sources.append((rel, src))
    manifest_files = {rel: _sha256(p) for rel, p in staged_sources}
    manifest = MigrationManifest(
        schema_version=SCHEMA_VERSION,
        format=FORMAT,
        created_at=datetime.now(timezone.utc).isoformat(),
        source_version=source_version,
        files=manifest_files,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(destination.parent), suffix=".nvra.tmp")
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest.to_dict(), indent=2, sort_keys=True))
            for rel, path in staged_sources:
                zf.write(path, rel)
        os.replace(tmp, destination)
    finally:
        tmp.unlink(missing_ok=True)
    return manifest


def inspect_migration_bundle(bundle_path: str | Path) -> MigrationManifest:
    """Verify archive paths and every payload checksum without extracting."""
    bundle_path = Path(bundle_path)
    if not bundle_path.is_file():
        raise MigrationError("bundle_not_found")
    with zipfile.ZipFile(bundle_path, "r") as zf:
        try:
            raw = zf.read("manifest.json")
            data = json.loads(raw.decode("utf-8"))
        except (KeyError, OSError, json.JSONDecodeError) as exc:
            raise MigrationError(f"invalid_manifest:{exc}") from exc
        if data.get("format") != FORMAT or int(data.get("schema_version", 0)) != SCHEMA_VERSION:
            raise MigrationError("unsupported_bundle_schema")
        files = dict(data.get("files") or {})
        names = set(zf.namelist())
        expected = set(files) | {"manifest.json"}
        if names != expected:
            raise MigrationError("archive_manifest_mismatch")
        for rel, expected_hash in files.items():
            if not _allowed(rel) or Path(rel).is_absolute() or ".." in Path(rel).parts:
                raise MigrationError(f"unsafe_archive_path:{rel}")
            with zf.open(rel, "r") as f:
                h = hashlib.sha256()
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
            if h.hexdigest() != expected_hash:
                raise MigrationError(f"checksum_mismatch:{rel}")
        return MigrationManifest(
            schema_version=SCHEMA_VERSION,
            format=FORMAT,
            created_at=str(data.get("created_at", "")),
            source_version=str(data.get("source_version", "")),
            files=files,
        )


def restore_migration_bundle(
    bundle_path: str | Path,
    *,
    data_root: str | Path,
    replace: bool = False,
) -> MigrationManifest:
    """Restore a verified bundle atomically into the destination data root."""
    manifest = inspect_migration_bundle(bundle_path)
    root = Path(data_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="nvra-restore-", dir=str(root.parent)))
    try:
        with zipfile.ZipFile(bundle_path, "r") as zf:
            for rel in manifest.files:
                target = (staging / rel).resolve()
                try:
                    target.relative_to(staging.resolve())
                except ValueError as exc:
                    raise MigrationError("path_escape") from exc
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(rel, "r") as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        # Re-verify staged content before touching live state.
        for rel, expected in manifest.files.items():
            if _sha256(staging / rel) != expected:
                raise MigrationError(f"staged_checksum_mismatch:{rel}")
        for rel in manifest.files:
            src = staging / rel
            dst = root / rel
            if dst.exists() and not replace:
                raise MigrationError(f"destination_exists:{rel}")
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return manifest
