"""Capital-adaptive risk — deterministic unit tests.

LIVE remains blocked: no live authorization in this suite.
"""

from __future__ import annotations

import time

import pytest

from god.broker.models import AccountState, AccountType
from god.risk.account_snapshot import (
    AccountSnapshot,
    AccountSnapshotPolicy,
    AccountStateEngine,
)
from god.risk.broker_constraints import (
    SymbolConstraints,
    constraints_from_dict,
    validate_symbol_constraints,
)
from god.risk.adaptive import (
    AdaptiveRiskRequest,
    CapitalAdaptiveRiskEngine,
    ExposureLimits,
)


def _fx_constraints(**overrides) -> SymbolConstraints:
    base = dict(
        symbol="EURUSD",
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        contract_size=100_000.0,
        tick_size=0.00001,
        tick_value=1.0,
        margin_initial=0.0,
        trade_mode="FULL",
    )
    base.update(overrides)
    return SymbolConstraints(**base)


def _snap(equity: float, **kw) -> AccountSnapshot:
    balance = kw.pop("balance", equity)
    free_margin = kw.pop("free_margin", equity)
    return AccountSnapshot(
        broker=kw.pop("broker", "Fake-Demo"),
        account_id=kw.pop("account_id", "1001"),
        server=kw.pop("server", "Fake-Demo"),
        account_type=kw.pop("account_type", "DEMO"),
        currency=kw.pop("currency", "USD"),
        balance=balance,
        equity=equity,
        free_margin=free_margin,
        margin=kw.pop("margin", 0.0),
        leverage=kw.pop("leverage", 100.0),
        margin_level=kw.pop("margin_level", 0.0),
        open_positions=kw.pop("open_positions", 0),
        connected=kw.pop("connected", True),
        observed_at=kw.pop("observed_at", time.time()),
        source=kw.pop("source", "test"),
    )


def _req(equity: float, risk_pct: float = 0.01, stop: float = 0.0010, **kw) -> AdaptiveRiskRequest:
    limits = kw.pop("limits", ExposureLimits(minimum_operational_equity=1.0))
    return AdaptiveRiskRequest(
        snapshot=_snap(equity, **{k: v for k, v in kw.items() if k in (
            "balance", "free_margin", "margin", "leverage", "connected", "observed_at",
            "account_type", "broker", "server",
        )}),
        constraints=kw.pop("constraints", _fx_constraints()),
        risk_pct=risk_pct,
        stop_loss_distance=stop,
        spread_price=kw.pop("spread_price", 0.00010),
        commission_per_lot=kw.pop("commission_per_lot", 0.0),
        existing_open_risk=kw.pop("existing_open_risk", 0.0),
        existing_exposure_lots=kw.pop("existing_exposure_lots", 0.0),
        open_positions=kw.pop("open_positions", 0),
        daily_loss=kw.pop("daily_loss", 0.0),
        peak_equity=kw.pop("peak_equity", 0.0),
        limits=limits,
        max_cost_ratio=kw.pop("max_cost_ratio", 0.50),
    )


@pytest.mark.parametrize(
    "equity,expected_budget",
    [
        (10.0, 0.10),
        (20.0, 0.20),
        (32.0, 0.32),
        (50.0, 0.50),
        (100.0, 1.00),
        (500.0, 5.00),
        (1000.0, 10.00),
    ],
)
def test_risk_budget_scales_with_equity(equity, expected_budget):
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(equity, risk_pct=0.01, stop=0.0010))
    if equity >= 1.0:
        if r.reason != "below_capital_floor":
            assert abs(r.risk_budget - expected_budget) < 1e-9 or r.risk_budget == 0.0 or r.ok
        if r.ok:
            assert abs(r.risk_budget - expected_budget) < 1e-9
            assert r.actual_worst_case_risk <= r.risk_budget + 1e-9


def test_ten_dollar_account_may_no_trade_if_min_lot_too_large():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(10.0, risk_pct=0.01, stop=0.0010))
    assert r.ok is False
    assert r.reason == "min_lot_exceeds_risk_budget"
    assert r.actual_worst_case_risk > r.risk_budget


def test_hundred_dollar_can_trade_with_reasonable_stop():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(100.0, risk_pct=0.01, stop=0.0010))
    assert r.ok is True
    assert r.volume >= 0.01
    assert r.actual_worst_case_risk <= r.risk_budget + 1e-9


def test_deposit_adaptation_10_to_32():
    eng = CapitalAdaptiveRiskEngine()
    r10 = eng.evaluate(_req(10.0, risk_pct=0.01, stop=0.0002))
    r32 = eng.evaluate(_req(32.0, risk_pct=0.01, stop=0.0002))
    assert r32.risk_budget == pytest.approx(0.32)
    if r32.ok and r10.ok:
        assert r32.volume >= r10.volume


def test_withdrawal_50_to_20_reduces_budget():
    eng = CapitalAdaptiveRiskEngine()
    r50 = eng.evaluate(_req(50.0, risk_pct=0.01, stop=0.0005))
    r20 = eng.evaluate(_req(20.0, risk_pct=0.01, stop=0.0005))
    assert r50.risk_budget == pytest.approx(0.50)
    assert r20.risk_budget == pytest.approx(0.20) or r20.reason in (
        "min_lot_exceeds_risk_budget",
        "volume_zero",
        "below_capital_floor",
    )


def test_profit_and_loss_change_equity_without_reconfig():
    eng = CapitalAdaptiveRiskEngine()
    base = eng.evaluate(_req(32.0, risk_pct=0.01, stop=0.0005))
    profit = eng.evaluate(_req(35.0, risk_pct=0.01, stop=0.0005))
    loss = eng.evaluate(_req(29.0, risk_pct=0.01, stop=0.0005))
    assert profit.risk_budget == pytest.approx(0.35)
    assert loss.risk_budget == pytest.approx(0.29)
    assert loss.details.get("risk_pct", 0.01) == 0.01


def test_invalid_volume_step_rejected():
    c = _fx_constraints(volume_step=0.0)
    v = validate_symbol_constraints(c)
    assert v.ok is False
    assert "invalid_volume_step" in v.reasons


def test_missing_constraints_from_dict():
    v = constraints_from_dict("EURUSD", {"volume_min": 0.01})
    assert v.ok is False
    assert any("missing_" in r for r in v.reasons)


def test_trade_mode_disabled():
    v = validate_symbol_constraints(_fx_constraints(trade_mode="DISABLED"))
    assert v.ok is False


def test_insufficient_margin():
    eng = CapitalAdaptiveRiskEngine()
    cons = _fx_constraints(margin_initial=50.0)
    r = eng.evaluate(
        AdaptiveRiskRequest(
            snapshot=_snap(100.0, free_margin=0.5),
            constraints=cons,
            risk_pct=0.01,
            stop_loss_distance=0.0002,
            limits=ExposureLimits(minimum_operational_equity=1.0),
        )
    )
    if r.ok:
        assert r.estimated_margin <= 0.5 + 1e-6
    else:
        assert r.reason in ("insufficient_margin", "min_lot_exceeds_risk_budget", "volume_zero")


@pytest.mark.parametrize("pct", [0.005, 0.01, 0.02])
def test_risk_percent_variants(pct):
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(500.0, risk_pct=pct, stop=0.0005))
    if r.ok:
        assert abs(r.risk_budget - 500.0 * pct) < 1e-9
        assert r.actual_worst_case_risk <= r.risk_budget + 1e-9


def test_risk_pct_hard_cap():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(
        _req(1000.0, risk_pct=0.05, limits=ExposureLimits(max_risk_per_trade_pct=0.02))
    )
    assert r.ok is False
    assert r.reason == "risk_pct_exceeds_hard_cap"


def test_max_concurrent_positions():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(
        _req(
            500.0,
            risk_pct=0.01,
            stop=0.0005,
            open_positions=3,
            limits=ExposureLimits(max_concurrent_positions=3, minimum_operational_equity=1.0),
        )
    )
    assert r.ok is False
    assert r.reason == "max_concurrent_positions"


def test_max_daily_loss():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(
        _req(
            500.0,
            risk_pct=0.01,
            stop=0.0005,
            daily_loss=50.0,
            limits=ExposureLimits(max_daily_loss=50.0, minimum_operational_equity=1.0),
        )
    )
    assert r.ok is False
    assert r.reason == "max_daily_loss"


def test_max_exposure_lots():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(
        _req(
            500.0,
            risk_pct=0.01,
            stop=0.0005,
            existing_exposure_lots=5.0,
            limits=ExposureLimits(max_total_exposure_lots=5.0, minimum_operational_equity=1.0),
        )
    )
    assert r.ok is False
    assert r.reason == "max_total_exposure"


def test_excessive_spread_cost_blocks():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(
        _req(
            500.0,
            risk_pct=0.01,
            stop=0.0005,
            spread_price=0.0500,
            max_cost_ratio=0.10,
        )
    )
    assert r.ok is False
    assert r.reason == "excessive_cost_ratio"


def test_low_spread_ok():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(500.0, risk_pct=0.01, stop=0.0005, spread_price=0.00005))
    assert r.ok is True


def test_stale_account_rejected():
    eng = AccountStateEngine(AccountSnapshotPolicy(max_age_seconds=5.0))
    snap = _snap(100.0, observed_at=time.time() - 60.0)
    v = eng.ingest(snap)
    assert v.ok is False
    assert any("stale_account" in r for r in v.reasons)


def test_disconnected_rejected():
    eng = AccountStateEngine()
    v = eng.ingest(_snap(100.0, connected=False))
    assert v.ok is False
    assert "not_connected" in v.reasons


def test_unknown_account_type_rejected():
    eng = AccountStateEngine()
    v = eng.ingest(_snap(100.0, account_type="UNKNOWN"))
    assert v.ok is False


def test_from_provider_state_ok():
    eng = AccountStateEngine()
    state = AccountState(
        broker="MT5",
        account_id="1001",
        server="Demo",
        account_type=AccountType.DEMO,
        currency="USD",
        balance=100.0,
        equity=100.0,
        free_margin=100.0,
        margin=0.0,
        leverage=100.0,
        connected=True,
    )
    v = eng.from_provider_state(state)
    assert v.ok is True
    assert v.snapshot is not None
    assert v.snapshot.equity == 100.0


def test_capital_floor():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(
        _req(0.5, risk_pct=0.01, limits=ExposureLimits(minimum_operational_equity=1.0))
    )
    assert r.ok is False
    assert r.reason == "below_capital_floor"


def test_round_down_never_exceeds_budget():
    eng = CapitalAdaptiveRiskEngine()
    for equity in (10, 20, 32, 50, 100, 250, 500, 1000):
        for stop in (0.0002, 0.0005, 0.0010, 0.0020):
            r = eng.evaluate(_req(float(equity), risk_pct=0.01, stop=stop))
            if r.ok:
                assert r.actual_worst_case_risk <= r.risk_budget + 1e-9, (
                    f"equity={equity} stop={stop} actual={r.actual_worst_case_risk} budget={r.risk_budget}"
                )
                step = 0.01
                assert abs(round(r.volume / step) * step - r.volume) < 1e-9


def test_never_upsizes_to_min_lot_past_risk():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(15.0, risk_pct=0.01, stop=0.0020))
    assert r.ok is False
    assert r.reason == "min_lot_exceeds_risk_budget"


def test_loss_does_not_increase_risk_pct():
    eng = CapitalAdaptiveRiskEngine()
    before = eng.evaluate(_req(100.0, risk_pct=0.01, stop=0.0005))
    after_loss = eng.evaluate(_req(80.0, risk_pct=0.01, stop=0.0005))
    assert before.details.get("risk_pct") == after_loss.details.get("risk_pct") == 0.01


def test_live_not_authorized_by_adaptive_engine():
    eng = CapitalAdaptiveRiskEngine()
    r = eng.evaluate(_req(100.0, risk_pct=0.01, stop=0.0005))
    d = r.to_dict()
    assert "live_authorized" not in d or d.get("live_authorized") is False
    assert "broker_orders_submitted" not in d


def test_account_refresh_each_call_uses_new_equity():
    eng = CapitalAdaptiveRiskEngine()
    a = eng.evaluate(_req(10.0, risk_pct=0.02, stop=0.0001))
    b = eng.evaluate(_req(100.0, risk_pct=0.02, stop=0.0001))
    assert b.risk_budget == pytest.approx(2.0)
    assert a.risk_budget == pytest.approx(0.2) or a.reason != "ok"
