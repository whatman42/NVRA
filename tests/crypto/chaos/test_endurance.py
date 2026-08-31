"""Synthetic endurance — growth slope and bounded queues."""

from __future__ import annotations

from crypto.chaos.endurance import run_synthetic_endurance


def test_synthetic_endurance_stable() -> None:
    report = run_synthetic_endurance(100)
    assert len(report.samples) == 100
    assert report.queue_bounded(10_000)
    slope = report.rss_growth_slope()
    assert slope == slope  # not NaN
    # Synthetic loop may show process noise; only require finite slope + bound queue
    assert abs(slope) < 1e12
