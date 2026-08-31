"""ProductionGate, micro-capital, GO/NO-GO — no LIVE exchange calls."""

from __future__ import annotations

from crypto.execution.models import ExecutionMode
from crypto.production import (
    CanaryState,
    LiveDecision,
    MicroCapitalLimits,
    ProductionGate,
    clamp_to_hard_ceiling,
)


def test_default_mode_paper() -> None:
    g = ProductionGate()
    assert g.default_mode() is ExecutionMode.PAPER


def test_software_green_without_exchange() -> None:
    g = ProductionGate(
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        withdrawal_status="DISABLED",
        canary_round_trip_ok=False,
        emergency_stop_tested=False,
    )
    report = g.evaluate(exchange_verified=False)
    assert report.software_green is True
    assert report.live_decision is LiveDecision.NOT_VERIFIED
    assert g.allow_live_submission(report) is False


def test_no_go_on_critical() -> None:
    g = ProductionGate(
        db_integrity=lambda: False,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        withdrawal_status="DISABLED",
    )
    report = g.evaluate(exchange_verified=True)
    assert report.software_green is False
    assert report.live_decision is LiveDecision.NO_GO


def test_withdrawal_enabled_blocks() -> None:
    g = ProductionGate(
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        withdrawal_status="ENABLED",
        canary_round_trip_ok=True,
        emergency_stop_tested=True,
    )
    report = g.evaluate(exchange_verified=True)
    assert any(c.name == "withdrawal_disabled" and not c.passed for c in report.checks)
    assert report.live_decision is LiveDecision.NO_GO


def test_force_live_cannot_bypass_hash(tmp_path) -> None:  # type: ignore[no-untyped-def]
    exe = tmp_path / "CRYPTO.exe"
    exe.write_bytes(b"fake-binary-content-v1")
    g = ProductionGate(
        executable_path=exe,
        expected_build_hash="deadbeef",
        force_live_flag=True,
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        withdrawal_status="DISABLED",
        canary_round_trip_ok=True,
        emergency_stop_tested=True,
    )
    report = g.evaluate(exchange_verified=True)
    assert any(c.name == "build_hash" and not c.passed for c in report.checks)
    assert report.live_decision is LiveDecision.NO_GO


def test_micro_capital_hard_ceiling() -> None:
    lim = MicroCapitalLimits(max_order_notional=99999, max_total_exposure=99999)
    c = clamp_to_hard_ceiling(lim)
    assert c.max_order_notional <= 500
    assert c.max_total_exposure <= 2000


def test_canary_round_trip_state() -> None:
    c = CanaryState()
    c.mark_buy_submitted("e1")
    c.mark_buy_filled()
    c.mark_sell_submitted("e2")
    c.mark_sell_filled()
    c.mark_reconciled()
    assert c.round_trip_ok is True


def test_go_when_all_green() -> None:
    g = ProductionGate(
        connectivity=lambda: True,
        permissions=lambda: {"trading": "ENABLED", "withdrawal": "DISABLED"},
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        time_skew_ms=100,
        withdrawal_status="DISABLED",
        canary_round_trip_ok=True,
        emergency_stop_tested=True,
        unresolved_unknown=False,
        reconciliation_mismatch=False,
    )
    report = g.evaluate(exchange_verified=True)
    assert report.live_decision is LiveDecision.GO
    assert g.allow_live_submission(report) is True


def test_unknown_withdrawal_blocks_live() -> None:
    g = ProductionGate(
        connectivity=lambda: True,
        permissions=lambda: {"trading": "ENABLED", "withdrawal": "UNKNOWN"},
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        time_skew_ms=0,
        withdrawal_status="UNKNOWN",
        canary_round_trip_ok=True,
        emergency_stop_tested=True,
    )
    report = g.evaluate(exchange_verified=True)
    assert report.live_decision is LiveDecision.NO_GO
    assert any(c.name == "withdrawal_disabled" and not c.passed for c in report.checks)


def test_live_requires_real_probes() -> None:
    g = ProductionGate(
        db_integrity=lambda: True,
        model_ok=lambda: True,
        recovery_ok=lambda: True,
        governor_ok=lambda: True,
        risk_ok=lambda: True,
        control_ok=lambda: True,
        withdrawal_status="DISABLED",
        canary_round_trip_ok=True,
        emergency_stop_tested=True,
    )
    report = g.evaluate(exchange_verified=True)
    assert report.live_decision is LiveDecision.NO_GO
    assert any(c.name == "live_connectivity_probe" for c in report.checks)
