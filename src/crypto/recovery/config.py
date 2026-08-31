"""Typed recovery / watchdog configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ComponentHeartbeatConfig:
    interval_seconds: float
    miss_tolerance: int
    progress_timeout_seconds: float


@dataclass(frozen=True, slots=True)
class RecoveryConfig:
    # Heartbeat baselines
    critical: ComponentHeartbeatConfig = field(
        default_factory=lambda: ComponentHeartbeatConfig(2.0, 2, 10.0)
    )
    normal: ComponentHeartbeatConfig = field(
        default_factory=lambda: ComponentHeartbeatConfig(5.0, 3, 30.0)
    )
    background: ComponentHeartbeatConfig = field(
        default_factory=lambda: ComponentHeartbeatConfig(10.0, 3, 60.0)
    )
    diagnostic_grace_seconds: float = 2.0

    # Recovery levels (backoff base seconds)
    level1_base_seconds: float = 5.0
    level2_base_seconds: float = 12.0
    level3_base_seconds: float = 30.0
    level4_base_seconds: float = 60.0
    level5_base_seconds: float = 120.0

    level1_max_attempts: int = 3
    level2_max_attempts: int = 3
    level3_max_attempts: int = 2
    level4_max_attempts: int = 2
    level5_max_attempts: int = 1

    # Circuit breaker
    storm_max_events: int = 5
    storm_window_seconds: float = 300.0

    # UNKNOWN order verification schedule (seconds from start)
    unknown_verify_schedule: tuple[float, ...] = (0.0, 2.0, 5.0, 10.0, 20.0, 30.0)

    # Startup API
    startup_max_concurrency: int = 2
    startup_min_interval_seconds: float = 0.25

    # SQLite
    sqlite_busy_timeout_ms: int = 5000
    use_wal: bool = True

    def validate(self) -> None:
        if self.diagnostic_grace_seconds < 0:
            raise ValueError("diagnostic_grace_seconds must be >= 0")
        if self.storm_max_events < 1:
            raise ValueError("storm_max_events must be >= 1")
