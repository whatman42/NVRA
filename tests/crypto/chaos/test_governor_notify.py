"""Governor resource-only + notification P0 priority under burst."""

from __future__ import annotations

from crypto.governor import GovernorThresholds, ResourceGovernor, ResourceSample
from crypto.hardware.models import ResourceBudget
from crypto.notify import NotifyPriority, NotifyQueue
from crypto.risk.policy import RiskPolicy


def _budget() -> ResourceBudget:
    return ResourceBudget(
        recommended_workers=2,
        max_workers=4,
        max_ml_models=2,
        max_universe=100,
        max_candidates=50,
        max_ml_candidates=20,
        max_predictions_per_cycle=10,
        max_opportunities=5,
        prediction_cache_size=32,
        feature_cache_size=32,
        market_cache_size=64,
        ohlcv_cache_size=32,
        max_features=20,
        max_training_rows=1000,
        memory_pressure_warning_bytes=10**9,
        memory_pressure_critical_bytes=2 * 10**9,
        ml_profile_name="LITE",
    )


def test_governor_does_not_change_risk() -> None:
    class C:
        t = 0.0

        def __call__(self) -> float:
            return self.t

        def adv(self, s: float) -> None:
            self.t += s

    clock = C()
    gov = ResourceGovernor(
        _budget(),
        GovernorThresholds(min_dwell_seconds=1.0),
        now_fn=clock,
    )
    before = RiskPolicy()
    clock.adv(5)
    sample = ResourceSample(
        timestamp_ms=1,
        cpu_utilization=0.99,
        ram_total_bytes=2 * 10**9,
        ram_available_bytes=50 * 10**6,
        process_rss_bytes=10**8,
        swap_used_bytes=10**7,
        io_wait_ratio=None,
        disk_latency_ms=300.0,
        network_latency_ms=2000.0,
        network_errors=3,
        queue_depth=1000,
        queue_age_ms=5000.0,
        cpu_temp_c=95.0,
        on_battery=False,
    )
    snap = gov.evaluate(sample)
    after = RiskPolicy()
    assert before.max_position_pct == after.max_position_pct
    assert snap.ring0.name == "PROTECTED"


def test_notify_p0_under_burst() -> None:
    q = NotifyQueue(rate_per_minute=2)
    for i in range(20):
        q.publish("telemetry", f"t{i}", priority=NotifyPriority.P3)
    q.publish("EMERGENCY", "STOP", priority=NotifyPriority.P0)
    first = q.pop_ready()
    assert first is not None
    assert first.priority is NotifyPriority.P0
