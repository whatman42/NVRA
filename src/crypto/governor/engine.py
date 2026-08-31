"""Dynamic Resource Governor — computational authority only."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from crypto.governor.budgets import AdaptiveBudget, scale_budget
from crypto.governor.config import GovernorThresholds
from crypto.governor.freshness import MarketDataFreshnessGate
from crypto.governor.states import (
    DEGRADATION_LEVELS,
    DataFreshness,
    GovernorState,
    MemoryPressure,
    RingStatus,
    ring0_status,
    ring1_status,
    ring2_status,
)
from crypto.governor.telemetry import ResourceSample, sample_resources
from crypto.hardware.models import ResourceBudget


@dataclass
class GovernorEvent:
    timestamp_ms: int
    event: str
    detail: str
    state: str


@dataclass
class GovernorSnapshot:
    timestamp_ms: int
    state: GovernorState
    degradation_level: int
    cpu_usage: float | None
    ram_usage: float | None  # used fraction 0..1
    memory_pressure: MemoryPressure
    swap_pressure: bool | None
    io_wait: float | None
    disk_latency_ms: float | None
    network_latency_ms: float | None
    network_errors: int | None
    queue_depth: int | None
    queue_age_ms: float | None
    thermal_state: str
    power_state: str
    ring0: RingStatus
    ring1: RingStatus
    ring2: RingStatus
    current_workers: int
    max_workers: int
    adaptive: AdaptiveBudget
    data_mode: str  # normal | coalesced
    events_tail: tuple[str, ...] = ()

    def summary_lines(self) -> list[str]:
        cpu = f"{self.cpu_usage * 100:.0f}%" if self.cpu_usage is not None else "UNKNOWN"
        ram = f"{self.ram_usage * 100:.0f}%" if self.ram_usage is not None else "UNKNOWN"
        return [
            f"State: {self.state.name}",
            f"CPU: {cpu}",
            f"RAM: {ram}",
            f"Disk latency: {self.disk_latency_ms if self.disk_latency_ms is not None else 'UNKNOWN'} ms",
            f"Network: {self.network_latency_ms if self.network_latency_ms is not None else 'UNKNOWN'} ms",
            f"ML models: {self.adaptive.max_ml_models}",
            f"Scanner ML candidates: {self.adaptive.max_ml_candidates}",
            f"Ring 0: {self.ring0.name}",
            f"Ring 1: {self.ring1.name}",
            f"Ring 2: {self.ring2.name}",
            "Risk: (unchanged — financial authority separate)",
        ]


class ResourceGovernor:
    """Adapts computational workload. Never mutates RiskPolicy."""

    def __init__(
        self,
        base_budget: ResourceBudget,
        thresholds: GovernorThresholds | None = None,
        *,
        now_fn: Any = None,
    ) -> None:
        self._base = base_budget
        self._t = thresholds or GovernorThresholds()
        self._t.validate()
        self._now = now_fn or time.monotonic
        self._state = GovernorState.NORMAL
        # Use the injected clock for all governor dwell timing.  This keeps
        # deterministic tests and monotonic runtime timing on the same clock.
        self._state_entered_at = self._now()
        self._pressure_since: float | None = None
        self._recovery_since: float | None = None
        self._events: list[GovernorEvent] = []
        self._freshness = MarketDataFreshnessGate(self._t)
        self._last_sample: ResourceSample | None = None
        self._adaptive = scale_budget(base_budget, GovernorState.NORMAL)

    @property
    def state(self) -> GovernorState:
        return self._state

    @property
    def adaptive_budget(self) -> AdaptiveBudget:
        return self._adaptive

    @property
    def freshness_gate(self) -> MarketDataFreshnessGate:
        return self._freshness

    def evaluate(
        self,
        sample: ResourceSample | None = None,
        *,
        queue_depth: int | None = None,
        queue_age_ms: float | None = None,
        network_latency_ms: float | None = None,
        network_errors: int | None = None,
        disk_latency_ms: float | None = None,
    ) -> GovernorSnapshot:
        """Ingest telemetry and possibly transition state."""
        if sample is None:
            sample = sample_resources(
                queue_depth=queue_depth,
                queue_age_ms=queue_age_ms,
                network_latency_ms=network_latency_ms,
                network_errors=network_errors,
                disk_latency_ms=disk_latency_ms,
            )
        self._last_sample = sample
        desired = self._desired_state(sample)
        self._maybe_transition(desired)
        self._adaptive = scale_budget(
            self._base,
            self._state,
            coalesce_degraded_ms=self._t.coalesce_degraded_ms,
            coalesce_constrained_ms=self._t.coalesce_constrained_ms,
        )
        return self.snapshot()

    def _desired_state(self, s: ResourceSample) -> GovernorState:
        """Map telemetry → severity target (before hysteresis)."""
        pressure_score = 0  # 0 normal, 1 degraded, 2 constrained, 3 critical

        if s.cpu_utilization is not None:
            if s.cpu_utilization >= self._t.cpu_scale_down:
                pressure_score = max(pressure_score, 1)
            if s.cpu_utilization >= 0.97:
                pressure_score = max(pressure_score, 2)

        mem_p = self._memory_pressure(s)
        if mem_p is MemoryPressure.WARNING:
            pressure_score = max(pressure_score, 1)
        elif mem_p is MemoryPressure.CRITICAL:
            pressure_score = max(pressure_score, 3)

        if s.disk_latency_ms is not None:
            if s.disk_latency_ms >= self._t.io_latency_scale_down_ms:
                pressure_score = max(pressure_score, 1)
            if s.disk_latency_ms >= self._t.io_latency_scale_down_ms * 2:
                pressure_score = max(pressure_score, 2)

        if s.network_latency_ms is not None:
            if s.network_latency_ms >= self._t.net_latency_scale_down_ms:
                pressure_score = max(pressure_score, 1)
            if s.network_latency_ms >= self._t.net_latency_scale_down_ms * 2:
                pressure_score = max(pressure_score, 2)

        if s.queue_depth is not None and s.queue_depth >= self._t.queue_depth_scale_down:
            pressure_score = max(pressure_score, 1)
            if s.queue_depth >= self._t.queue_depth_scale_down * 3:
                pressure_score = max(pressure_score, 2)

        if s.cpu_temp_c is not None and s.cpu_temp_c >= 90:
            pressure_score = max(pressure_score, 2)
        if s.on_battery is True:
            pressure_score = max(pressure_score, 1)

        return {
            0: GovernorState.NORMAL,
            1: GovernorState.DEGRADED,
            2: GovernorState.CONSTRAINED,
            3: GovernorState.CRITICAL,
        }[pressure_score]

    def _memory_pressure(self, s: ResourceSample) -> MemoryPressure:
        if s.ram_available_bytes is None or s.ram_total_bytes is None:
            return MemoryPressure.UNKNOWN
        free = s.ram_available_bytes
        total = max(1, s.ram_total_bytes)
        frac = free / total
        if free <= self._t.ram_free_critical_bytes or frac < self._t.ram_free_scale_down * 0.5:
            return MemoryPressure.CRITICAL
        if free <= self._t.ram_free_warning_bytes or frac < self._t.ram_free_scale_down:
            return MemoryPressure.WARNING
        return MemoryPressure.NORMAL

    def _maybe_transition(self, desired: GovernorState) -> None:
        now = self._now()
        elapsed = now - self._state_entered_at
        severity = {
            GovernorState.NORMAL: 0,
            GovernorState.DEGRADED: 1,
            GovernorState.RECOVERY: 1,
            GovernorState.CONSTRAINED: 2,
            GovernorState.CRITICAL: 3,
        }
        cur_sev = severity[self._state]
        des_sev = severity[desired]

        # Scale-down: allow faster (respect min dwell only lightly)
        if des_sev > cur_sev:
            if elapsed < min(5.0, self._t.min_dwell_seconds):
                return  # brief dwell even on scale-down
            self._set_state(desired, now, f"pressure→{desired.name}")
            self._pressure_since = now
            self._recovery_since = None
            return

        # Scale-up: need stability at reduced pressure
        if des_sev < cur_sev:
            if elapsed < self._t.min_dwell_seconds:
                return
            # Enter RECOVERY first from CRITICAL/CONSTRAINED
            if (
                self._state is GovernorState.CRITICAL
                and desired
                in (
                    GovernorState.NORMAL,
                    GovernorState.DEGRADED,
                    GovernorState.CONSTRAINED,
                )
                and self._recovery_since is None
            ):
                self._set_state(GovernorState.RECOVERY, now, "enter recovery")
                self._recovery_since = now
                return
            if self._state is GovernorState.RECOVERY:
                if (
                    self._recovery_since
                    and (now - self._recovery_since) < self._t.recovery_stability_seconds
                ):
                    return
                # recovery complete → step toward desired
                if desired is GovernorState.NORMAL:
                    self._set_state(GovernorState.DEGRADED, now, "recovery→degraded")
                    return
                self._set_state(desired, now, f"recovery→{desired.name}")
                self._recovery_since = None
                return

            # From DEGRADED/CONSTRAINED toward better
            if (
                self._pressure_since is not None
                and (now - self._state_entered_at) < self._t.recovery_stability_seconds
            ):
                # need recovery stability of low pressure
                return
            if self._state is GovernorState.CONSTRAINED and desired is GovernorState.NORMAL:
                self._set_state(GovernorState.DEGRADED, now, "step up degraded")
                return
            self._set_state(desired, now, f"scale-up→{desired.name}")
            self._pressure_since = None
            return

        # same severity — if in RECOVERY and still ok, continue timer
        if (
            self._state is GovernorState.RECOVERY
            and desired is GovernorState.NORMAL
            and self._recovery_since
            and (now - self._recovery_since) >= self._t.recovery_stability_seconds
        ):
            self._set_state(GovernorState.DEGRADED, now, "recovery stable→degraded")

    def _set_state(self, new: GovernorState, now: float, detail: str) -> None:
        if new is self._state:
            return
        old = self._state
        self._state = new
        self._state_entered_at = now
        self._adaptive = scale_budget(self._base, new)
        self._emit("GOVERNOR_STATE_CHANGED", f"{old.name}→{new.name} ({detail})")
        if new is GovernorState.DEGRADED:
            self._emit("ML_DEGRADED", "ensemble reduced")
            self._emit("SCANNER_DEGRADED", "candidate budget reduced")
        if new in (GovernorState.CONSTRAINED, GovernorState.CRITICAL):
            self._emit("RING2_SUSPENDED", "expendable work stopped")
            self._emit("RING1_DEGRADED", "elastic work reduced")
        if new is GovernorState.CRITICAL:
            self._emit("RESOURCE_PRESSURE", "critical compute only")
        if old in (GovernorState.CRITICAL, GovernorState.CONSTRAINED) and severity_rank(
            new
        ) < severity_rank(old):
            self._emit("RESOURCE_RECOVERY", f"recovering via {new.name}")

    def _emit(self, event: str, detail: str) -> None:
        self._events.append(
            GovernorEvent(
                timestamp_ms=int(time.time() * 1000),
                event=event,
                detail=detail[:500],
                state=self._state.name,
            )
        )
        if len(self._events) > 200:
            self._events = self._events[-100:]

    def admit(self, work: str) -> bool:
        """Admission control for expensive computational tasks."""
        if work == "training":
            return self._adaptive.admit_training
        if work == "large_scan":
            return self._adaptive.admit_large_scan
        if work == "ring2":
            return self._adaptive.ring2_enabled
        return True

    def allow_strategy_proposal(self, last_market_data_ms: int | None) -> bool:
        """Stale-data gate for new proposals (not financial risk)."""
        freshness = self._freshness.evaluate(last_market_data_ms)
        if not self._freshness.allow_new_proposal(freshness):
            self._emit("STALE_DATA_BLOCK", f"freshness={freshness.name}")
            return False
        if self._state is GovernorState.CRITICAL:
            # still allow only if data fresh — ring0 path separate
            return freshness is DataFreshness.FRESH
        return True

    def snapshot(self) -> GovernorSnapshot:
        s = self._last_sample
        ram_usage = None
        mem_p = MemoryPressure.UNKNOWN
        swap_p = None
        if s is not None:
            mem_p = self._memory_pressure(s)
            if s.ram_total_bytes and s.ram_available_bytes is not None:
                ram_usage = 1.0 - (s.ram_available_bytes / max(1, s.ram_total_bytes))
            if s.swap_used_bytes is not None:
                swap_p = s.swap_used_bytes > 0

        thermal = "UNKNOWN"
        power = "UNKNOWN"
        if s is not None:
            if s.cpu_temp_c is not None:
                thermal = "HOT" if s.cpu_temp_c >= 85 else "OK"
            if s.on_battery is True:
                power = "BATTERY"
            elif s.on_battery is False:
                power = "AC"

        data_mode = "coalesced" if self._adaptive.coalesce_interval_ms > 0 else "normal"
        tail = tuple(e.event for e in self._events[-5:])

        return GovernorSnapshot(
            timestamp_ms=int(time.time() * 1000),
            state=self._state,
            degradation_level=DEGRADATION_LEVELS.get(self._state, 0),
            cpu_usage=s.cpu_utilization if s else None,
            ram_usage=ram_usage,
            memory_pressure=mem_p,
            swap_pressure=swap_p,
            io_wait=s.io_wait_ratio if s else None,
            disk_latency_ms=s.disk_latency_ms if s else None,
            network_latency_ms=s.network_latency_ms if s else None,
            network_errors=s.network_errors if s else None,
            queue_depth=s.queue_depth if s else None,
            queue_age_ms=s.queue_age_ms if s else None,
            thermal_state=thermal,
            power_state=power,
            ring0=ring0_status(self._state),
            ring1=ring1_status(self._state),
            ring2=ring2_status(self._state),
            current_workers=self._adaptive.workers,
            max_workers=self._base.max_workers,
            adaptive=self._adaptive,
            data_mode=data_mode,
            events_tail=tail,
        )


def severity_rank(state: GovernorState) -> int:
    return {
        GovernorState.NORMAL: 0,
        GovernorState.DEGRADED: 1,
        GovernorState.RECOVERY: 1,
        GovernorState.CONSTRAINED: 2,
        GovernorState.CRITICAL: 3,
    }[state]
