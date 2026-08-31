"""Self-healing controller — detect → lock → recover → verify → reconcile → unlock.

Execution stays locked until READY after successful reconciliation.
No trading intelligence.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional, Sequence

from god.bridge.installer import EAInstaller, InstallResult
from god.bridge.integrity import IntegrityReport, verify_artifact
from god.bridge.lifecycle import DeploymentState, DeploymentStatus
from god.bridge.models import TerminalInstance
from god.bridge.manager import BridgeManager
from god.bridge.reconciliation import ReconciliationReport

logger = logging.getLogger(__name__)


class FailureKind(str, Enum):
    EA_MISSING = "EA_MISSING"
    EA_CORRUPTED = "EA_CORRUPTED"
    TERMINAL_MOVED = "TERMINAL_MOVED"
    IPC_DISCONNECTED = "IPC_DISCONNECTED"
    RECONCILE_FAILED = "RECONCILE_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class RecoveryReport:
    success: bool
    failure: FailureKind
    steps: list[str] = field(default_factory=list)
    install: Optional[InstallResult] = None
    integrity: Optional[IntegrityReport] = None
    reconciliation: Optional[ReconciliationReport] = None
    final_state: DeploymentState = DeploymentState.FAILED
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "failure": self.failure.value,
            "steps": list(self.steps),
            "final_state": self.final_state.value,
            "message": self.message,
            "install_action": self.install.action.value if self.install else None,
            "integrity_ok": self.integrity.ok if self.integrity else None,
            "reconcile_ok": (
                self.reconciliation.success if self.reconciliation is not None else None
            ),
        }


class SelfHealingController:
    """Orchestrates detect → install/verify → reconnect → reconcile → READY.

    Does not call broker execution APIs. Does not implement strategy.
    """

    def __init__(
        self,
        installer: Optional[EAInstaller] = None,
        *,
        discover: Optional[Callable[[], Sequence[TerminalInstance]]] = None,
        max_recovery_attempts: int = 3,
    ) -> None:
        self.installer = installer or EAInstaller()
        self._discover = discover
        self.max_recovery_attempts = max_recovery_attempts
        self.status = DeploymentStatus(state=DeploymentState.DISCOVERY)

    def bind_terminal(self, terminal: TerminalInstance) -> None:
        self.status.terminal_id = terminal.terminal_id
        self.status.platform = (
            terminal.platform.value if hasattr(terminal.platform, "value") else str(terminal.platform)
        )
        self._terminal = terminal

    @property
    def terminal(self) -> Optional[TerminalInstance]:
        return getattr(self, "_terminal", None)

    def detect_failure(self, terminal: Optional[TerminalInstance] = None) -> FailureKind:
        """Inspect EA file and return failure kind (or UNKNOWN if ok)."""
        t = terminal or self.terminal
        if t is None:
            return FailureKind.UNKNOWN
        try:
            target = self.installer.target_ea_path(t)
            spec = self.installer.registry.get_spec(t.platform)
            report = verify_artifact(target, spec)
            if report.result.value == "MISSING":
                return FailureKind.EA_MISSING
            if not report.ok:
                return FailureKind.EA_CORRUPTED
            return FailureKind.UNKNOWN
        except Exception as e:
            logger.debug("detect_failure error: %s", e)
            return FailureKind.UNKNOWN

    def ensure_installed(self, terminal: Optional[TerminalInstance] = None) -> InstallResult:
        """Install if missing/corrupt; skip if integrity ok."""
        t = terminal or self.terminal
        if t is None:
            from god.bridge.installer.models import InstallAction
            return InstallResult(success=False, action=InstallAction.FAILED, error="no terminal bound")
        self.status.set_state(DeploymentState.INSTALLING)
        result = self.installer.install(t)
        if result.success and result.record:
            self.status.ea_path = result.record.target_path
            self.status.ea_version = result.record.version
            self.status.ea_sha256 = result.record.sha256
            self.status.set_state(DeploymentState.VERIFYING)
            verify = self.installer.verify(t)
            if verify.success:
                return result
            self.status.set_state(DeploymentState.FAILED, error=verify.error)
            return verify
        self.status.set_state(DeploymentState.FAILED, error=result.error)
        return result

    def recover(
        self,
        *,
        manager: Optional[BridgeManager] = None,
        terminal: Optional[TerminalInstance] = None,
        failure: Optional[FailureKind] = None,
        brain_positions: Optional[list] = None,
        skip_ipc: bool = False,
    ) -> RecoveryReport:
        """Full recovery sequence with execution lock until READY.

        skip_ipc=True allows unit tests without a live transport.
        """
        t = terminal or self.terminal
        steps: list[str] = []
        kind = failure or (self.detect_failure(t) if t else FailureKind.UNKNOWN)
        steps.append(f"detect:{kind.value}")

        self.status.set_state(DeploymentState.RECOVERY)
        self.status.execution_locked = True
        self.status.reconnect_count += 1

        if t is None:
            return RecoveryReport(
                success=False,
                failure=kind,
                steps=steps,
                final_state=DeploymentState.FAILED,
                message="no terminal",
            )

        if kind == FailureKind.TERMINAL_MOVED and self._discover is not None:
            steps.append("rediscover")
            found = list(self._discover())
            match = next((x for x in found if x.platform == t.platform), None)
            if match is None:
                self.status.set_state(DeploymentState.FAILED, error="rediscover empty")
                return RecoveryReport(
                    success=False,
                    failure=kind,
                    steps=steps,
                    final_state=DeploymentState.FAILED,
                    message="rediscover found no terminal",
                )
            t = match
            self.bind_terminal(t)

        steps.append("install_or_verify")
        install = self.ensure_installed(t)
        if not install.success:
            return RecoveryReport(
                success=False,
                failure=kind,
                steps=steps,
                install=install,
                final_state=DeploymentState.FAILED,
                message=install.error or "install failed",
            )
        steps.append(f"install:{install.action.value}")

        integrity = None
        try:
            target = self.installer.target_ea_path(t)
            spec = self.installer.registry.get_spec(t.platform)
            integrity = verify_artifact(target, spec)
            steps.append(f"integrity:{integrity.result.value}")
            if not integrity.ok:
                self.status.set_state(DeploymentState.FAILED, error=integrity.message)
                return RecoveryReport(
                    success=False,
                    failure=FailureKind.EA_CORRUPTED,
                    steps=steps,
                    install=install,
                    integrity=integrity,
                    final_state=DeploymentState.FAILED,
                    message=integrity.message,
                )
        except Exception as e:
            steps.append(f"integrity_error:{e}")
            self.status.set_state(DeploymentState.FAILED, error=str(e))
            return RecoveryReport(
                success=False,
                failure=kind,
                steps=steps,
                install=install,
                final_state=DeploymentState.FAILED,
                message=str(e),
            )

        reconcile_report = None
        if not skip_ipc and manager is not None:
            steps.append("connect")
            self.status.set_state(DeploymentState.CONNECTING)
            try:
                manager.terminal = t
                manager.connect(timeout=5.0)
                steps.append("connected")
            except Exception as e:
                self.status.set_state(DeploymentState.DEGRADED, error=str(e))
                return RecoveryReport(
                    success=False,
                    failure=FailureKind.IPC_DISCONNECTED,
                    steps=steps,
                    install=install,
                    integrity=integrity,
                    final_state=DeploymentState.DEGRADED,
                    message=f"connect failed: {e}",
                )

            steps.append("reconcile")
            self.status.set_state(DeploymentState.RECONCILING)
            try:
                reconcile_report = manager.reconcile(brain_positions or [])
                ok = bool(getattr(reconcile_report, "success", True))
                steps.append(f"reconcile_ok:{ok}")
                if reconcile_report is not None and not ok:
                    self.status.set_state(DeploymentState.FAILED, error="reconciliation mismatch")
                    return RecoveryReport(
                        success=False,
                        failure=FailureKind.RECONCILE_FAILED,
                        steps=steps,
                        install=install,
                        integrity=integrity,
                        reconciliation=reconcile_report,
                        final_state=DeploymentState.FAILED,
                        message="reconciliation failed",
                    )
            except Exception as e:
                self.status.set_state(DeploymentState.FAILED, error=str(e))
                return RecoveryReport(
                    success=False,
                    failure=FailureKind.RECONCILE_FAILED,
                    steps=steps,
                    install=install,
                    integrity=integrity,
                    final_state=DeploymentState.FAILED,
                    message=f"reconcile error: {e}",
                )
        else:
            steps.append("skip_ipc")

        self.status.set_state(DeploymentState.READY)
        steps.append("READY")
        return RecoveryReport(
            success=True,
            failure=kind,
            steps=steps,
            install=install,
            integrity=integrity,
            reconciliation=reconcile_report,
            final_state=DeploymentState.READY,
            message="recovery complete",
        )

    def bring_to_ready(
        self,
        terminal: TerminalInstance,
        *,
        manager: Optional[BridgeManager] = None,
        brain_positions: Optional[list] = None,
        skip_ipc: bool = False,
    ) -> RecoveryReport:
        """Happy path: install → verify → ready."""
        self.bind_terminal(terminal)
        self.status.set_state(DeploymentState.DISCOVERY)
        return self.recover(
            manager=manager,
            terminal=terminal,
            failure=self.detect_failure(terminal),
            brain_positions=brain_positions,
            skip_ipc=skip_ipc,
        )
