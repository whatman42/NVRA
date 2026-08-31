"""Supervisor / watchdog — independent of monitored components."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from crypto.recovery.backoff import backoff_seconds
from crypto.recovery.circuit import RecoveryCircuitBreaker
from crypto.recovery.config import ComponentHeartbeatConfig, RecoveryConfig
from crypto.recovery.events import RecoveryEvent, make_event
from crypto.recovery.health import (
    ComponentClass,
    ComponentHealth,
    HealthState,
)
from crypto.recovery.safe_mode import SafeModeController
from crypto.recovery.unknown import UnknownOrderResolver


@dataclass
class SupervisorSnapshot:
    safe_mode: bool
    safe_mode_reason: str
    components: dict[str, str]
    recovery_storm: bool
    events_tail: tuple[str, ...]


class Supervisor:
    """Heartbeat monitor + hierarchical recovery + safe mode."""

    def __init__(
        self,
        config: RecoveryConfig | None = None,
        *,
        mono_fn: Callable[[], float] | None = None,
        rng_seed: int | None = 42,
    ) -> None:
        self._cfg = config or RecoveryConfig()
        self._cfg.validate()
        self._mono = mono_fn or time.monotonic
        self._components: dict[str, ComponentHealth] = {}
        self._safe = SafeModeController()
        self._breaker = RecoveryCircuitBreaker(
            self._cfg.storm_max_events,
            self._cfg.storm_window_seconds,
            mono_fn=self._mono,
        )
        self._unknown = UnknownOrderResolver(self._cfg)
        self._events: list[RecoveryEvent] = []
        self._rng_seed = rng_seed

    @property
    def safe_mode(self) -> SafeModeController:
        return self._safe

    @property
    def unknown_resolver(self) -> UnknownOrderResolver:
        return self._unknown

    def register(
        self,
        component_id: str,
        component_class: ComponentClass = ComponentClass.NORMAL,
    ) -> ComponentHealth:
        h = ComponentHealth(
            component_id=component_id,
            component_class=component_class,
            last_heartbeat_mono=self._mono(),
            last_progress_mono=self._mono(),
        )
        self._components[component_id] = h
        return h

    def heartbeat(self, component_id: str, *, operation: str | None = None) -> None:
        h = self._components.get(component_id)
        if h is None:
            return
        h.beat(mono=self._mono(), operation=operation)
        if h.health in (HealthState.SUSPECT, HealthState.UNRESPONSIVE):
            h.health = HealthState.HEALTHY

    def progress(self, component_id: str, operation: str = "") -> None:
        h = self._components.get(component_id)
        if h is None:
            return
        h.progress(mono=self._mono(), operation=operation)
        if h.health is HealthState.DEGRADED:
            h.health = HealthState.HEALTHY

    def tick(self) -> list[RecoveryEvent]:
        """Evaluate heartbeats using monotonic time. Returns new events."""
        now = self._mono()
        new_events: list[RecoveryEvent] = []
        for h in self._components.values():
            cfg = self._cfg_for(h.component_class)
            hb_timeout = cfg.interval_seconds * (cfg.miss_tolerance + 1)
            # Progress stuck detection
            if h.current_operation and h.operation_start_mono is not None:
                stuck_for = now - h.last_progress_mono
                if stuck_for > cfg.progress_timeout_seconds:
                    h.consecutive_progress_misses += 1
                    if h.health is HealthState.HEALTHY:
                        h.health = HealthState.DEGRADED
                        ev = make_event(
                            "COMPONENT_STUCK",
                            h.component_id,
                            f"op={h.current_operation} stuck={stuck_for:.1f}s",
                        )
                        new_events.append(ev)
                        self._events.append(ev)

            age = now - h.last_heartbeat_mono
            if age > hb_timeout:
                h.consecutive_heartbeat_misses += 1
                if h.health is HealthState.HEALTHY or h.health is HealthState.DEGRADED:
                    h.health = HealthState.SUSPECT
                    ev = make_event(
                        "HEARTBEAT_MISSED",
                        h.component_id,
                        f"age={age:.1f}s → SUSPECT",
                    )
                    new_events.append(ev)
                    self._events.append(ev)
                elif h.health is HealthState.SUSPECT:
                    # diagnostic grace
                    if age > hb_timeout + self._cfg.diagnostic_grace_seconds:
                        h.health = HealthState.UNRESPONSIVE
                        ev = make_event(
                            "COMPONENT_SUSPECT",
                            h.component_id,
                            "diagnostic failed → UNRESPONSIVE",
                        )
                        new_events.append(ev)
                        self._events.append(ev)
                        self._begin_recovery(h)

        return new_events

    def _cfg_for(self, cls: ComponentClass) -> ComponentHeartbeatConfig:
        if cls is ComponentClass.CRITICAL:
            return self._cfg.critical
        if cls is ComponentClass.BACKGROUND:
            return self._cfg.background
        return self._cfg.normal

    def _begin_recovery(self, h: ComponentHealth) -> None:
        if self._breaker.is_open or self._breaker.record():
            self._safe.enter("RECOVERY_STORM", mono=self._mono())
            self._events.append(make_event("RECOVERY_STORM", h.component_id, "circuit open"))
            self._events.append(make_event("SAFE_MODE_ENTERED", "supervisor", "recovery storm"))
            h.health = HealthState.SAFE_MODE
            return

        h.health = HealthState.RECOVERING
        h.recovery_level = max(1, h.recovery_level)
        self._events.append(
            make_event(
                "RECOVERY_STARTED",
                h.component_id,
                f"level={h.recovery_level}",
                level=h.recovery_level,
            )
        )

    def recover_component(
        self,
        component_id: str,
        recover_fn: Callable[[int], bool],
    ) -> bool:
        """Attempt hierarchical recovery. recover_fn(level) → success."""
        h = self._components.get(component_id)
        if h is None:
            return False
        if self._breaker.is_open:
            self._safe.enter("RECOVERY_STORM", mono=self._mono())
            return False

        max_attempts = {
            1: self._cfg.level1_max_attempts,
            2: self._cfg.level2_max_attempts,
            3: self._cfg.level3_max_attempts,
            4: self._cfg.level4_max_attempts,
            5: self._cfg.level5_max_attempts,
        }
        bases = {
            1: self._cfg.level1_base_seconds,
            2: self._cfg.level2_base_seconds,
            3: self._cfg.level3_base_seconds,
            4: self._cfg.level4_base_seconds,
            5: self._cfg.level5_base_seconds,
        }

        level = max(1, min(5, h.recovery_level or 1))
        attempts_at_level = h.recovery_attempts

        if attempts_at_level >= max_attempts.get(level, 1):
            if level >= 5:
                self._safe.enter(f"recovery exhausted for {component_id}", mono=self._mono())
                h.health = HealthState.SAFE_MODE
                self._events.append(
                    make_event("RECOVERY_FAILED", component_id, "exhausted → SAFE_MODE")
                )
                return False
            h.recovery_level = level + 1
            h.recovery_attempts = 0
            self._events.append(
                make_event(
                    "RECOVERY_ESCALATED",
                    component_id,
                    f"level→{h.recovery_level}",
                    level=h.recovery_level,
                )
            )
            level = h.recovery_level

        # backoff (caller may sleep; we report delay)
        delay = backoff_seconds(bases.get(level, 5.0), attempts_at_level)
        h.recovery_attempts += 1
        self._events.append(
            make_event(
                "RECOVERY_RETRY",
                component_id,
                f"level={level} attempt={h.recovery_attempts} delay={delay:.1f}s",
                level=level,
            )
        )

        if self._breaker.record():
            self._safe.enter("RECOVERY_STORM", mono=self._mono())
            self._events.append(make_event("RECOVERY_STORM", component_id, "during recover"))
            return False

        try:
            ok = recover_fn(level)
        except Exception as exc:  # noqa: BLE001
            h.last_error = type(exc).__name__
            ok = False

        if ok:
            h.health = HealthState.HEALTHY
            h.recovery_level = 0
            h.recovery_attempts = 0
            h.beat(mono=self._mono())
            h.progress(mono=self._mono())
            self._events.append(make_event("RECOVERY_SUCCEEDED", component_id, f"level={level}"))
            return True

        h.health = HealthState.FAILED
        self._events.append(make_event("RECOVERY_FAILED", component_id, f"level={level}"))
        return False

    def enter_safe_mode(self, reason: str) -> None:
        self._safe.enter(reason, mono=self._mono())
        for h in self._components.values():
            if h.component_class is ComponentClass.BACKGROUND:
                h.health = HealthState.SAFE_MODE

    def try_exit_safe_mode(
        self,
        *,
        components_healthy: bool,
        exchange_ok: bool,
        reconciliation_ok: bool,
        execution_consistent: bool,
        market_data_fresh: bool,
        no_unresolved_critical: bool,
    ) -> bool:
        return self._safe.try_exit(
            components_healthy=components_healthy,
            exchange_ok=exchange_ok,
            reconciliation_ok=reconciliation_ok,
            execution_consistent=execution_consistent,
            market_data_fresh=market_data_fresh,
            no_unresolved_critical=no_unresolved_critical,
            mono=self._mono(),
        )

    def blocks_new_entries(self) -> bool:
        return self._safe.blocks_new_entries()

    def snapshot(self) -> SupervisorSnapshot:
        return SupervisorSnapshot(
            safe_mode=self._safe.active,
            safe_mode_reason=self._safe.reason,
            components={k: v.health.name for k, v in self._components.items()},
            recovery_storm=self._breaker.is_open,
            events_tail=tuple(e.event for e in self._events[-8:]),
        )

    def events(self) -> list[RecoveryEvent]:
        return list(self._events)
