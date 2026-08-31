"""Typed governor thresholds — hysteresis and dwell."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GovernorThresholds:
    # CPU (0..1 utilization)
    cpu_scale_down: float = 0.90
    cpu_scale_up: float = 0.65
    # RAM: free fraction of total
    ram_free_scale_down: float = 0.12  # free < 12% → pressure
    ram_free_scale_up: float = 0.25
    # Absolute free RAM floors (bytes) — critical on small machines
    ram_free_critical_bytes: int = 200 * 1024 * 1024  # 200 MiB
    ram_free_warning_bytes: int = 400 * 1024 * 1024
    # I/O latency (ms)
    io_latency_scale_down_ms: float = 200.0
    io_latency_scale_up_ms: float = 80.0
    # Network latency (ms)
    net_latency_scale_down_ms: float = 1500.0
    net_latency_scale_up_ms: float = 400.0
    # Queue
    queue_depth_scale_down: int = 500
    queue_depth_scale_up: int = 100
    # Hysteresis / dwell
    min_dwell_seconds: float = 30.0
    recovery_stability_seconds: float = 120.0
    # Market data freshness (seconds since last update)
    data_aging_seconds: float = 5.0
    data_stale_seconds: float = 15.0
    data_critical_stale_seconds: float = 60.0
    # Coalescing under pressure (ms)
    coalesce_degraded_ms: int = 250
    coalesce_constrained_ms: int = 500

    def validate(self) -> None:
        if self.cpu_scale_up >= self.cpu_scale_down:
            raise ValueError("cpu_scale_up must be < cpu_scale_down")
        if self.ram_free_scale_up <= self.ram_free_scale_down:
            raise ValueError("ram_free_scale_up must be > ram_free_scale_down")
        if self.min_dwell_seconds < 0 or self.recovery_stability_seconds < 0:
            raise ValueError("dwell/stability must be >= 0")
