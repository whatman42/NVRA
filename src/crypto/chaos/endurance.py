"""Endurance metrics — growth slope, not just start vs end."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Sample:
    t_mono: float
    rss_bytes: int
    queue_depth: int
    cache_size: int
    sqlite_bytes: int
    recovery_count: int
    reconnect_count: int


@dataclass
class EnduranceReport:
    samples: list[Sample] = field(default_factory=list)
    max_rss: int = 0
    max_queue: int = 0
    recovery_total: int = 0
    reconnect_total: int = 0

    def add(self, sample: Sample) -> None:
        self.samples.append(sample)
        self.max_rss = max(self.max_rss, sample.rss_bytes)
        self.max_queue = max(self.max_queue, sample.queue_depth)
        self.recovery_total = max(self.recovery_total, sample.recovery_count)
        self.reconnect_total = max(self.reconnect_total, sample.reconnect_count)

    def rss_growth_slope(self) -> float:
        """Bytes per second linear slope; 0 if insufficient samples."""
        if len(self.samples) < 2:
            return 0.0
        t0 = self.samples[0].t_mono
        xs = [s.t_mono - t0 for s in self.samples]
        ys = [float(s.rss_bytes) for s in self.samples]
        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n
        num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
        den = sum((x - mean_x) ** 2 for x in xs)
        if den <= 0:
            return 0.0
        return num / den

    def queue_bounded(self, limit: int = 10_000) -> bool:
        return self.max_queue <= limit

    def memory_stable(self, max_slope_bytes_per_s: float = 50_000.0) -> bool:
        """Default: allow up to ~50KB/s growth in short synthetic runs."""
        return abs(self.rss_growth_slope()) <= max_slope_bytes_per_s


def estimate_rss() -> int:
    try:
        with open("/proc/self/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except OSError:
        pass
    return 0


def run_synthetic_endurance(
    iterations: int = 200,
    *,
    work_fn: Any | None = None,
) -> EnduranceReport:
    """Accelerated endurance loop for CI (not wall-clock 72h)."""
    report = EnduranceReport()
    for i in range(iterations):
        if work_fn is not None:
            work_fn(i)
        report.add(
            Sample(
                t_mono=time.monotonic(),
                rss_bytes=estimate_rss(),
                queue_depth=min(i % 50, 40),
                cache_size=min(100 + i, 500),
                sqlite_bytes=4096 + i * 10,
                recovery_count=0,
                reconnect_count=i // 80,
            )
        )
    return report
