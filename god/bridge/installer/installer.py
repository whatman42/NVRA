"""EAInstaller — atomic, idempotent deploy of thin NUNG Bridge EA.

Flow:
  TEMP FILE → WRITE → FLUSH → VERIFY CHECKSUM → ATOMIC REPLACE

Never leaves a partially written EA as the active artifact.
No trading intelligence.
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional

from god.bridge.integrity import (
    ArtifactSpec,
    IntegrityResult,
    sha256_file,
    verify_artifact,
)
from god.bridge.models import Platform, TerminalInstance
from god.bridge.artifacts.registry import ArtifactRegistry, get_default_registry
from god.memory.database import utc_now

from .errors import ArtifactNotFoundError, ExpertsPathError, IntegrityInstallError, InstallerError
from .models import DeploymentRecord, InstallAction, InstallResult

logger = logging.getLogger(__name__)


class EAInstaller:
    """Deploy NUNG_Bridge.ex4 / .ex5 into a terminal's Experts directory."""

    def __init__(
        self,
        *,
        registry: Optional[ArtifactRegistry] = None,
        path_exists: Optional[Callable[[str], bool]] = None,
        is_dir: Optional[Callable[[str], bool]] = None,
        mkdir: Optional[Callable[[str], None]] = None,
        atomic_replace: Optional[Callable[[str, str], None]] = None,
    ) -> None:
        self.registry = registry or get_default_registry()
        self._path_exists = path_exists or (lambda p: Path(p).exists())
        self._is_dir = is_dir or (lambda p: Path(p).is_dir())
        self._mkdir = mkdir or (lambda p: Path(p).mkdir(parents=True, exist_ok=True))
        self._atomic_replace = atomic_replace or _default_atomic_replace

    def resolve_experts_path(self, terminal: TerminalInstance) -> str:
        """Return Experts directory for the terminal; raise if unknown."""
        if terminal.experts_path and self._is_dir(terminal.experts_path):
            return terminal.experts_path
        if terminal.experts_path:
            parent = str(Path(terminal.experts_path).parent)
            if self._path_exists(parent) or self._is_dir(parent):
                self._mkdir(terminal.experts_path)
                return terminal.experts_path
        inferred = _infer_experts(terminal)
        if inferred:
            if not self._is_dir(inferred):
                self._mkdir(inferred)
            return inferred
        raise ExpertsPathError(
            f"cannot resolve Experts path for terminal {terminal.terminal_id} "
            f"(platform={terminal.platform})"
        )

    def target_ea_path(self, terminal: TerminalInstance) -> str:
        experts = self.resolve_experts_path(terminal)
        spec = self.registry.get_spec(terminal.platform)
        return str(Path(experts) / spec.name)

    def install(
        self,
        terminal: TerminalInstance,
        *,
        force: bool = False,
    ) -> InstallResult:
        """Install or reinstall EA. Idempotent unless force or integrity mismatch."""
        try:
            if terminal.platform not in (Platform.MT4, Platform.MT5):
                return InstallResult(
                    success=False,
                    action=InstallAction.FAILED,
                    error=f"unsupported platform: {terminal.platform}",
                )

            spec = self.registry.get_spec(terminal.platform)
            data = self.registry.get_bytes(terminal.platform)
            if not data:
                raise ArtifactNotFoundError(f"no artifact bytes for {terminal.platform}")

            experts = self.resolve_experts_path(terminal)
            target = str(Path(experts) / spec.name)

            if not force and self._path_exists(target):
                report = verify_artifact(target, spec)
                if report.ok:
                    record = DeploymentRecord(
                        terminal_id=terminal.terminal_id,
                        platform=terminal.platform,
                        target_path=target,
                        artifact_name=spec.name,
                        version=spec.version,
                        sha256=spec.sha256,
                        size_bytes=spec.size_bytes,
                        deployed_at=utc_now(),
                        action=InstallAction.SKIPPED_IDEMPOTENT,
                        integrity=IntegrityResult.OK,
                    )
                    logger.info("EA already installed and verified: %s", target)
                    return InstallResult(
                        success=True,
                        action=InstallAction.SKIPPED_IDEMPOTENT,
                        record=record,
                        message="already installed, integrity ok",
                    )
                action = InstallAction.REPLACED
            else:
                action = InstallAction.INSTALLED if not self._path_exists(target) else InstallAction.REINSTALLED

            self._write_atomic(target, data, spec)

            report = verify_artifact(target, spec)
            if not report.ok:
                raise IntegrityInstallError(report.message)

            record = DeploymentRecord(
                terminal_id=terminal.terminal_id,
                platform=terminal.platform,
                target_path=target,
                artifact_name=spec.name,
                version=spec.version,
                sha256=spec.sha256,
                size_bytes=spec.size_bytes,
                deployed_at=utc_now(),
                action=action,
                integrity=IntegrityResult.OK,
            )
            logger.info("EA %s → %s (%s)", action.value, target, spec.sha256[:12])
            return InstallResult(
                success=True,
                action=action,
                record=record,
                message=f"{action.value}: {target}",
            )
        except InstallerError as e:
            logger.warning("install failed: %s", e)
            return InstallResult(
                success=False,
                action=InstallAction.FAILED,
                error=str(e),
            )
        except OSError as e:
            logger.warning("install OS error: %s", e)
            return InstallResult(
                success=False,
                action=InstallAction.FAILED,
                error=str(e),
            )

    def verify(self, terminal: TerminalInstance) -> InstallResult:
        """Verify installed EA against registry spec without writing."""
        try:
            spec = self.registry.get_spec(terminal.platform)
            target = self.target_ea_path(terminal)
            report = verify_artifact(target, spec)
            if report.ok:
                record = DeploymentRecord(
                    terminal_id=terminal.terminal_id,
                    platform=terminal.platform,
                    target_path=target,
                    artifact_name=spec.name,
                    version=spec.version,
                    sha256=spec.sha256,
                    size_bytes=spec.size_bytes,
                    deployed_at=utc_now(),
                    action=InstallAction.SKIPPED_IDEMPOTENT,
                    integrity=IntegrityResult.OK,
                )
                return InstallResult(
                    success=True,
                    action=InstallAction.SKIPPED_IDEMPOTENT,
                    record=record,
                    message="integrity ok",
                )
            return InstallResult(
                success=False,
                action=InstallAction.FAILED,
                error=report.message,
                message=report.result.value,
            )
        except Exception as e:
            return InstallResult(
                success=False,
                action=InstallAction.FAILED,
                error=str(e),
            )

    def _write_atomic(self, target: str, data: bytes, spec: ArtifactSpec) -> None:
        """Write to temp in same dir, verify, then atomic replace."""
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".nung_",
            suffix=".tmp",
            dir=str(target_path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            digest = sha256_file(tmp_name)
            if digest.lower() != spec.sha256.lower():
                raise IntegrityInstallError(
                    f"temp write checksum mismatch: {digest} != {spec.sha256}"
                )
            size = Path(tmp_name).stat().st_size
            if size != spec.size_bytes:
                raise IntegrityInstallError(
                    f"temp write size mismatch: {size} != {spec.size_bytes}"
                )
            self._atomic_replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def _default_atomic_replace(src: str, dst: str) -> None:
    """os.replace is atomic on same filesystem (POSIX + modern Windows)."""
    os.replace(src, dst)


def _infer_experts(terminal: TerminalInstance) -> Optional[str]:
    if terminal.data_path:
        base = Path(terminal.data_path)
        if terminal.platform == Platform.MT5:
            return str(base / "MQL5" / "Experts")
        if terminal.platform == Platform.MT4:
            return str(base / "MQL4" / "Experts")
    if terminal.executable_path:
        root = Path(terminal.executable_path).resolve().parent
        if terminal.platform == Platform.MT5:
            return str(root / "MQL5" / "Experts")
        if terminal.platform == Platform.MT4:
            return str(root / "MQL4" / "Experts")
    return None
