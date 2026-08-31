"""Infrastructure deployment lifecycle states for Phase 3B-B.

Safety rule: execution is only allowed in READY after successful reconciliation.
No trading intelligence lives here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DeploymentState(str, Enum):
    """EA / bridge deployment lifecycle.

    Execution must remain locked in all states except READY.
    """

    DISCOVERY = "DISCOVERY"
    INSTALLING = "INSTALLING"
    VERIFYING = "VERIFYING"
    CONNECTING = "CONNECTING"
    RECONCILING = "RECONCILING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    RECOVERY = "RECOVERY"
    FAILED = "FAILED"


# States in which real-money autonomous execution is forbidden.
EXECUTION_LOCKED_STATES = frozenset(
    {
        DeploymentState.DISCOVERY,
        DeploymentState.INSTALLING,
        DeploymentState.VERIFYING,
        DeploymentState.CONNECTING,
        DeploymentState.RECONCILING,
        DeploymentState.DEGRADED,
        DeploymentState.RECOVERY,
        DeploymentState.FAILED,
    }
)


@dataclass
class DeploymentStatus:
    """Current deployment/safety status for one terminal target."""

    state: DeploymentState = DeploymentState.DISCOVERY
    terminal_id: Optional[str] = None
    platform: Optional[str] = None
    ea_path: Optional[str] = None
    ea_version: Optional[str] = None
    ea_sha256: Optional[str] = None
    last_error: Optional[str] = None
    execution_locked: bool = True
    reconnect_count: int = 0
    metadata: dict = field(default_factory=dict)

    def set_state(self, state: DeploymentState, *, error: Optional[str] = None) -> None:
        self.state = state
        self.execution_locked = state in EXECUTION_LOCKED_STATES
        if error is not None:
            self.last_error = error
        elif state == DeploymentState.READY:
            self.last_error = None

    def allows_execution(self) -> bool:
        return self.state == DeploymentState.READY and not self.execution_locked

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "terminal_id": self.terminal_id,
            "platform": self.platform,
            "ea_path": self.ea_path,
            "ea_version": self.ea_version,
            "ea_sha256": self.ea_sha256,
            "last_error": self.last_error,
            "execution_locked": self.execution_locked,
            "reconnect_count": self.reconnect_count,
            "metadata": dict(self.metadata),
        }
