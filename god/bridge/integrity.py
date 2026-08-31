"""EA artifact integrity — SHA-256, version, size, expected vs actual.

No credentials. No trading logic.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class IntegrityResult(str, Enum):
    OK = "OK"
    MISSING = "MISSING"
    CORRUPTED = "CORRUPTED"
    MODIFIED = "MODIFIED"
    VERSION_MISMATCH = "VERSION_MISMATCH"
    SIZE_MISMATCH = "SIZE_MISMATCH"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ArtifactSpec:
    """Expected EA artifact identity."""

    name: str
    version: str
    sha256: str
    size_bytes: int
    platform: str  # MT4 / MT5
    source_label: str = "bundled"

    @property
    def filename(self) -> str:
        return self.name


@dataclass
class IntegrityReport:
    """Result of comparing expected vs actual EA on disk."""

    result: IntegrityResult
    expected: Optional[ArtifactSpec] = None
    actual_path: Optional[str] = None
    actual_sha256: Optional[str] = None
    actual_size: Optional[int] = None
    message: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.result == IntegrityResult.OK

    def to_dict(self) -> dict:
        return {
            "result": self.result.value,
            "ok": self.ok,
            "actual_path": self.actual_path,
            "actual_sha256": self.actual_sha256,
            "actual_size": self.actual_size,
            "message": self.message,
            "expected_name": self.expected.name if self.expected else None,
            "expected_version": self.expected.version if self.expected else None,
            "expected_sha256": self.expected.sha256 if self.expected else None,
            "metadata": dict(self.metadata),
        }


def sha256_file(path: str | Path, *, chunk_size: int = 65536) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_artifact(
    path: str | Path,
    expected: ArtifactSpec,
) -> IntegrityReport:
    """Compare file at path against expected ArtifactSpec."""
    p = Path(path)
    if not p.is_file():
        return IntegrityReport(
            result=IntegrityResult.MISSING,
            expected=expected,
            actual_path=str(p),
            message=f"EA artifact missing: {p}",
        )
    try:
        size = p.stat().st_size
        digest = sha256_file(p)
    except OSError as e:
        return IntegrityReport(
            result=IntegrityResult.UNKNOWN,
            expected=expected,
            actual_path=str(p),
            message=f"cannot read artifact: {e}",
        )

    if size != expected.size_bytes:
        return IntegrityReport(
            result=IntegrityResult.SIZE_MISMATCH,
            expected=expected,
            actual_path=str(p),
            actual_sha256=digest,
            actual_size=size,
            message=f"size mismatch: expected {expected.size_bytes}, got {size}",
        )
    if digest.lower() != expected.sha256.lower():
        return IntegrityReport(
            result=IntegrityResult.CORRUPTED
            if digest != expected.sha256
            else IntegrityResult.MODIFIED,
            expected=expected,
            actual_path=str(p),
            actual_sha256=digest,
            actual_size=size,
            message=f"checksum mismatch: expected {expected.sha256}, got {digest}",
        )
    return IntegrityReport(
        result=IntegrityResult.OK,
        expected=expected,
        actual_path=str(p),
        actual_sha256=digest,
        actual_size=size,
        message="integrity ok",
    )
