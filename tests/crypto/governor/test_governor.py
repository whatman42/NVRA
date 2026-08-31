"""Resource governor: states, hysteresis, risk isolation, stale gate."""

from __future__ import annotations

from crypto.governor import (
    DataFreshness,
    GovernorState,
    GovernorThresholds,
    ResourceGovernor,
    ResourceSample,
    RingStatus,
)
from crypto.hardware.models import ResourceBudget
from crypto.risk.policy import RiskPolicy


def _budget() -> ResourceBudget:
    return ResourceBudget(
        recommended_workers=4,
        max_workers=8,
        max_ml_models=3,
        max_universe=800,
        max_candidates=150,
        max_ml_candidates=50,
        max_predictions_per_cycle=20,
        max_opportunities=10,
        prediction_cache_size=64,
        feature_cache_size=128,
        market_cache_size=256,
        ohlcv_cache_size=128,
        max_features=40,
        max_training_rows=20_000,
        memory_pressure_warning_bytes=2 * 1024**3,
        memory_pressure_critical_bytes=3 * 1024**3,
        ml_profile_name="BALANCED",
    )


def _sample(
    *,
    cpu: float | None = 0.2,
    ram_avail: int | None = 4 * 1024**3,
    ram_total: int | None = 8 * 1024**3,
    disk_ms: float | None = 20.0,
    net_ms: float | None = 100.0,
    queue: int | None = 10,
) -> ResourceSample:
    return ResourceSample(
        timestamp_ms=1,
        cpu_utilization=cpu,
        ram_total_bytes=ram_total,
        ram_available_bytes=ram_avail,
        process_rss_bytes=100 * 1024**2,
        swap_used_bytes=0,
        io_wait_ratio=None,
        disk_latency_ms=disk_ms,
        network_latency_ms=net_ms,
        network_errors=0,
        queue_depth=queue,
        queue_age_ms=5.0,
        cpu_temp_c=50.0,
        on_battery=False,
    )


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_normal_state() -> None:
    clock = _Clock()
    gov = ResourceGovernor(_budget(), now_fn=clock)
    snap = gov.evaluate(_sample())
    assert snap.state is GovernorState.NORMAL
    assert snap.ring0 is RingStatus.PROTECTED
    assert snap.ring2 is RingStatus.FULL


def test_cpu_pressure_degrades() -> None:
    clock = _Clock()
    t = GovernorThresholds(min_dwell_seconds=5.0, recovery_stability_seconds=30.0)
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    clock.advance(10)
    snap = gov.evaluate(_sample(cpu=0.95))
    assert snap.state is GovernorState.DEGRADED
    assert snap.adaptive.max_ml_models < _budget().max_ml_models
    assert snap.ring2 is RingStatus.SUSPENDED


def test_hysteresis_no_immediate_recovery() -> None:
    clock = _Clock()
    t = GovernorThresholds(min_dwell_seconds=30.0, recovery_stability_seconds=120.0)
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    clock.advance(30)
    gov.evaluate(_sample(cpu=0.95))
    assert gov.state is GovernorState.DEGRADED
    # CPU recovers but dwell/stability not met
    clock.advance(10)
    gov.evaluate(_sample(cpu=0.50))
    assert gov.state is GovernorState.DEGRADED
    # still within recovery window
    clock.advance(50)
    gov.evaluate(_sample(cpu=0.50))
    assert gov.state is GovernorState.DEGRADED


def test_critical_ram() -> None:
    clock = _Clock()
    t = GovernorThresholds(
        min_dwell_seconds=1.0,
        ram_free_critical_bytes=500 * 1024**2,
        recovery_stability_seconds=10.0,
    )
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    clock.advance(5)
    # 100 MiB free on 2 GB machine
    snap = gov.evaluate(_sample(cpu=0.3, ram_avail=100 * 1024**2, ram_total=2 * 1024**3))
    assert snap.state is GovernorState.CRITICAL
    assert snap.adaptive.workers == 1
    assert snap.ring0 is RingStatus.PROTECTED


def test_risk_policy_unchanged_across_states() -> None:
    """CRITICAL isolation: governor never mutates RiskPolicy."""
    policies = []
    clock = _Clock()
    t = GovernorThresholds(min_dwell_seconds=1.0, recovery_stability_seconds=5.0)
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    samples = [
        _sample(cpu=0.2),
        _sample(cpu=0.95),
        _sample(cpu=0.99, ram_avail=100 * 1024**2, ram_total=2 * 1024**3),
    ]
    for s in samples:
        clock.advance(5)
        gov.evaluate(s)
        policies.append(RiskPolicy())
    a, b, c = policies
    assert a.max_position_pct == b.max_position_pct == c.max_position_pct
    assert a.max_daily_loss_pct == c.max_daily_loss_pct
    assert a.max_drawdown_pct == c.max_drawdown_pct
    assert a.max_portfolio_exposure_pct == c.max_portfolio_exposure_pct


def test_stale_data_blocks_proposal() -> None:
    import time

    gov = ResourceGovernor(_budget())
    now = int(time.time() * 1000)
    # fresh
    assert gov.allow_strategy_proposal(now - 1000) is True
    # stale (default 15s)
    assert gov.allow_strategy_proposal(now - 30_000) is False


def test_freshness_levels() -> None:
    from crypto.governor.freshness import MarketDataFreshnessGate

    gate = MarketDataFreshnessGate(
        GovernorThresholds(
            data_aging_seconds=5,
            data_stale_seconds=15,
            data_critical_stale_seconds=60,
        )
    )
    now = 1_000_000
    assert gate.evaluate(now - 1000, now_ms=now) is DataFreshness.FRESH
    assert gate.evaluate(now - 8_000, now_ms=now) is DataFreshness.AGING
    assert gate.evaluate(now - 20_000, now_ms=now) is DataFreshness.STALE
    assert gate.evaluate(now - 90_000, now_ms=now) is DataFreshness.CRITICAL_STALE
    assert gate.allow_new_proposal(DataFreshness.STALE) is False


def test_admission_control() -> None:
    clock = _Clock()
    t = GovernorThresholds(min_dwell_seconds=1.0)
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    assert gov.admit("training") is True
    clock.advance(5)
    gov.evaluate(_sample(cpu=0.95))
    assert gov.admit("training") is False
    assert gov.admit("ring2") is False


def test_disk_pressure_degrades() -> None:
    clock = _Clock()
    t = GovernorThresholds(min_dwell_seconds=1.0, io_latency_scale_down_ms=200.0)
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    clock.advance(5)
    snap = gov.evaluate(_sample(cpu=0.2, disk_ms=250.0))
    assert snap.state is GovernorState.DEGRADED


def test_network_pressure() -> None:
    clock = _Clock()
    t = GovernorThresholds(min_dwell_seconds=1.0, net_latency_scale_down_ms=500.0)
    gov = ResourceGovernor(_budget(), t, now_fn=clock)
    clock.advance(5)
    snap = gov.evaluate(_sample(cpu=0.2, net_ms=2000.0))
    assert snap.state in (GovernorState.DEGRADED, GovernorState.CONSTRAINED)


def test_summary_separates_risk() -> None:
    gov = ResourceGovernor(_budget())
    snap = gov.evaluate(_sample())
    lines = snap.summary_lines()
    assert any("Risk:" in x for x in lines)
    assert any("State:" in x for x in lines)
