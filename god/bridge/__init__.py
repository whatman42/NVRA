"""MT4/MT5 Execution Bridge — thin adapter between brain and terminals.

Phase 3B-A: discovery, protocol, IPC, heartbeat, reconciliation (mocked).
Phase 3B-B: EA installer, integrity, self-healing, deployment lifecycle.
No trading intelligence. EA remains a dumb body.
"""

from .models import (
    TerminalInstance,
    Platform,
    TerminalStatus,
    BridgeConnectionState,
    BridgeHealth,
)
from .protocols import BridgeProtocol
from .discovery import TerminalDiscovery
from .manager import BridgeManager
from .errors import (
    BridgeError,
    DiscoveryError,
    HandshakeError,
    IncompatibleVersionError,
    ReconciliationError,
)
from .lifecycle import DeploymentState, DeploymentStatus, EXECUTION_LOCKED_STATES
from .integrity import (
    ArtifactSpec,
    IntegrityReport,
    IntegrityResult,
    verify_artifact,
    sha256_file,
)
from .healing import SelfHealingController, RecoveryReport, FailureKind
from .installer import EAInstaller, InstallResult, InstallAction, DeploymentRecord

__all__ = [
    "TerminalInstance",
    "Platform",
    "TerminalStatus",
    "BridgeConnectionState",
    "BridgeHealth",
    "BridgeProtocol",
    "TerminalDiscovery",
    "BridgeManager",
    "BridgeError",
    "DiscoveryError",
    "HandshakeError",
    "IncompatibleVersionError",
    "ReconciliationError",
    "DeploymentState",
    "DeploymentStatus",
    "EXECUTION_LOCKED_STATES",
    "ArtifactSpec",
    "IntegrityReport",
    "IntegrityResult",
    "verify_artifact",
    "sha256_file",
    "SelfHealingController",
    "RecoveryReport",
    "FailureKind",
    "EAInstaller",
    "InstallResult",
    "InstallAction",
    "DeploymentRecord",
]
