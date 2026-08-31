"""Self-recovery, watchdog, crash-safe state (Phase 10)."""

from crypto.recovery.config import ComponentHeartbeatConfig, RecoveryConfig
from crypto.recovery.events import RecoveryEvent
from crypto.recovery.health import ComponentClass, ComponentHealth, HealthState
from crypto.recovery.safe_mode import SafeModeController
from crypto.recovery.startup import (
    StartupPhase,
    StartupRecovery,
    StartupResult,
    StartupTask,
    TaskPriority,
)
from crypto.recovery.storage import (
    StorageHealth,
    ensure_recovery_schema,
    integrity_check,
    open_hardened_db,
)
from crypto.recovery.supervisor import Supervisor, SupervisorSnapshot
from crypto.recovery.unknown import UnknownOrderResolver, UnknownResolution

__all__ = [
    "Supervisor",
    "SupervisorSnapshot",
    "RecoveryConfig",
    "ComponentHeartbeatConfig",
    "ComponentClass",
    "ComponentHealth",
    "HealthState",
    "SafeModeController",
    "UnknownOrderResolver",
    "UnknownResolution",
    "StartupRecovery",
    "StartupResult",
    "StartupTask",
    "StartupPhase",
    "TaskPriority",
    "RecoveryEvent",
    "StorageHealth",
    "integrity_check",
    "open_hardened_db",
    "ensure_recovery_schema",
]
