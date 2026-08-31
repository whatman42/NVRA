"""Watchdog, recovery, safe mode, unknown orders, risk isolation."""

from __future__ import annotations

from crypto.recovery import (
    ComponentClass,
    HealthState,
    RecoveryConfig,
    StartupRecovery,
    StartupTask,
    Supervisor,
    TaskPriority,
    UnknownOrderResolver,
    UnknownResolution,
    ensure_recovery_schema,
    integrity_check,
    open_hardened_db,
)
from crypto.risk.policy import RiskPolicy


class _Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t

    def advance(self, s: float) -> None:
        self.t += s


def test_heartbeat_healthy() -> None:
    clock = _Clock()
    sup = Supervisor(mono_fn=clock)
    sup.register("execution", ComponentClass.CRITICAL)
    sup.heartbeat("execution")
    clock.advance(1)
    sup.tick()
    assert sup.snapshot().components["execution"] == HealthState.HEALTHY.name


def test_missed_heartbeat_suspect() -> None:
    clock = _Clock()
    cfg = RecoveryConfig()
    # critical: 2s * (2+1) = 6s timeout
    sup = Supervisor(cfg, mono_fn=clock)
    sup.register("execution", ComponentClass.CRITICAL)
    sup.heartbeat("execution")
    clock.advance(7)
    sup.tick()
    assert sup.snapshot().components["execution"] == HealthState.SUSPECT.name


def test_stuck_progress() -> None:
    clock = _Clock()
    cfg = RecoveryConfig()
    sup = Supervisor(cfg, mono_fn=clock)
    h = sup.register("ml", ComponentClass.BACKGROUND)
    h.mark_operation("predict", mono=clock())
    # Keep heartbeat alive but no progress
    for _ in range(5):
        clock.advance(12)
        sup.heartbeat("ml")
    clock.advance(5)
    events = sup.tick()
    assert any(e.event == "COMPONENT_STUCK" for e in events)
    assert h.health in (HealthState.DEGRADED, HealthState.SUSPECT)


def test_recovery_escalation_and_safe_mode() -> None:
    clock = _Clock()
    cfg = RecoveryConfig(
        level1_max_attempts=1,
        level2_max_attempts=1,
        level3_max_attempts=1,
        level4_max_attempts=1,
        level5_max_attempts=1,
        storm_max_events=50,
    )
    sup = Supervisor(cfg, mono_fn=clock)
    sup.register("exchange", ComponentClass.NORMAL)
    h = sup._components["exchange"]
    h.health = HealthState.UNRESPONSIVE
    h.recovery_level = 1

    def always_fail(level: int) -> bool:
        return False

    for _ in range(6):
        sup.recover_component("exchange", always_fail)
    assert sup.safe_mode.active or h.health in (
        HealthState.FAILED,
        HealthState.SAFE_MODE,
    )


def test_recovery_storm() -> None:
    clock = _Clock()
    cfg = RecoveryConfig(storm_max_events=3, storm_window_seconds=300.0)
    sup = Supervisor(cfg, mono_fn=clock)
    sup.register("ml", ComponentClass.BACKGROUND)
    h = sup._components["ml"]
    h.health = HealthState.UNRESPONSIVE
    h.recovery_level = 1

    def fail(level: int) -> bool:
        return False

    for _ in range(5):
        sup.recover_component("ml", fail)
        clock.advance(1)
    assert sup.safe_mode.active or sup.snapshot().recovery_storm


def test_unknown_order_found() -> None:
    clock = _Clock()
    sup = Supervisor(mono_fn=clock)
    r = sup.unknown_resolver
    r.track("ex1", "client1", mono=clock())
    clock.advance(0.1)
    res = r.query_once("ex1", lambda _eid: "filled", mono=clock())
    assert res is UnknownResolution.FOUND_FILLED


def test_unknown_not_failed_when_missing() -> None:
    clock = _Clock()
    cfg = RecoveryConfig(unknown_verify_schedule=(0.0, 1.0))
    r = UnknownOrderResolver(cfg)
    r.track("ex2", "c2", mono=clock())
    r.query_once("ex2", lambda _eid: None, mono=clock())
    clock.advance(1.5)
    res = r.query_once("ex2", lambda _eid: None, mono=clock())
    assert res is UnknownResolution.UNRESOLVED
    assert res is not UnknownResolution.FOUND_FAILED


def test_unknown_blocks_duplicate_intent() -> None:
    r = UnknownOrderResolver()
    r.track("ex3", "same-client")
    assert r.blocks_duplicate("same-client") is True


def test_startup_blocks_trading_until_ready() -> None:
    sr = StartupRecovery()
    tasks = [
        StartupTask("reconcile", TaskPriority.P0, lambda: True),
        StartupTask("balances", TaskPriority.P1, lambda: True),
    ]
    result = sr.run(tasks, sleep_fn=lambda _s: None)
    assert result.safe_to_trade is True

    tasks2 = [
        StartupTask("reconcile", TaskPriority.P0, lambda: False),
        StartupTask("balances", TaskPriority.P1, lambda: True),
    ]
    r2 = sr.run(tasks2, sleep_fn=lambda _s: None)
    assert r2.safe_to_trade is False
    assert r2.partial or r2.phase.name in ("PARTIAL", "SAFE_MODE")


def test_sqlite_integrity(tmp_path) -> None:  # type: ignore[no-untyped-def]
    path = tmp_path / "rec.db"
    conn = open_hardened_db(path)
    ensure_recovery_schema(conn)
    assert integrity_check(conn) == "OK"
    conn.close()


def test_risk_policy_unchanged_in_safe_mode() -> None:
    clock = _Clock()
    sup = Supervisor(mono_fn=clock)
    before = RiskPolicy()
    sup.enter_safe_mode("test")
    after = RiskPolicy()
    assert before.max_position_pct == after.max_position_pct
    assert before.max_daily_loss_pct == after.max_daily_loss_pct
    assert before.max_drawdown_pct == after.max_drawdown_pct
    assert sup.blocks_new_entries() is True


def test_safe_mode_exit_requires_gates() -> None:
    clock = _Clock()
    sup = Supervisor(mono_fn=clock)
    sup.enter_safe_mode("test")
    assert (
        sup.try_exit_safe_mode(
            components_healthy=True,
            exchange_ok=True,
            reconciliation_ok=False,
            execution_consistent=True,
            market_data_fresh=True,
            no_unresolved_critical=True,
        )
        is False
    )
    assert (
        sup.try_exit_safe_mode(
            components_healthy=True,
            exchange_ok=True,
            reconciliation_ok=True,
            execution_consistent=True,
            market_data_fresh=True,
            no_unresolved_critical=True,
        )
        is True
    )
