"""Installer models — deployment records and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from god.bridge.integrity import ArtifactSpec, IntegrityResult
from god.bridge.models import Platform


class InstallAction(str, Enum):
    INSTALLED = "INSTALLED"
    SKIPPED_IDEMPOTENT = "SKIPPED_IDEMPOTENT"
    REPLACED = "REPLACED"
    REINSTALLED = "REINSTALLED"
    FAILED = "FAILED"


@dataclass
class DeploymentRecord:
    """Metadata about a deployed EA on a terminal."""

    terminal_id: str
    platform: Platform
    target_path: str
    artifact_name: str
    version: str
    sha256: str
    size_bytes: int
    deployed_at: str
    action: InstallAction = InstallAction.INSTALLED
    integrity: IntegrityResult = IntegrityResult.OK
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "terminal_id": self.terminal_id,
            "platform": self.platform.value if isinstance(self.platform, Platform) else self.platform,
            "target_path": self.target_path,
            "artifact_name": self.artifact_name,
            "version": self.version,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "deployed_at": self.deployed_at,
            "action": self.action.value,
            "integrity": self.integrity.value,
            "metadata": dict(self.metadata),
        }


@dataclass
class InstallResult:
    """Outcome of an install / reinstall attempt."""

    success: bool
    action: InstallAction
    record: Optional[DeploymentRecord] = None
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "action": self.action.value,
            "record": self.record.to_dict() if self.record else None,
            "message": self.message,
            "error": self.error,
        }
