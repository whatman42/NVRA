"""ExecutionEngine: paper path, idempotency, risk gate, recovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crypto.exchanges.errors import TradingDisabledError
from crypto.exchanges.models import AssetBalance
from crypto.execution import (
    ExecutionEngine,
    ExecutionError,
    ExecutionMode,
    ExecutionStore,
    OrderState,
    PaperBroker,
)
from crypto.market.quality import DataQuality, DataQualityReport
from crypto.portfolio import AccountKey, build_holdings, build_portfolio
from crypto.risk import (
    MarketConstraints,
    RiskEngine,
    RiskPolicy,
    RiskVerdict,
    SafetyMode,
    Side,
    TradeProposal,
)


def _portfolio(equity: float = 10_000.0) -> object:
    acct = AccountKey("binance", "default")
    holds = build_holdings(acct, [AssetBalance("USDT", equity, 0.0, equity)])
    return build_portfolio(accounts_holdings={acct: holds}, quote_currency="USDT")


def _decision(qty: float = 1.0, price: float = 100.0) -> object:
    eng = RiskEngine(RiskPolicy(max_position_pct=50.0))
    prop = TradeProposal(
        exchange_id="binance",
        account_id="default",
        symbol="BTC/USDT",
        side=Side.BUY,
        requested_quantity=qty,
        requested_price=price,
    )
    return eng.evaluate(
        prop,
        _portfolio(),
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=price,
    )


@pytest.fixture
def store(tmp_path: Path) -> ExecutionStore:
    return ExecutionStore(tmp_path / "exec.db")


@pytest.fixture
def mock_adapter() -> MagicMock:
    adapter = MagicMock()
    adapter.exchange_id = "binance"
    adapter.trading_enabled = False
    adapter.enable_trading = MagicMock()
    adapter.create_order = MagicMock(
        side_effect=TradingDisabledError("disabled", exchange_id="binance")
    )
    return adapter


def test_paper_submit_fills(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine(RiskPolicy(max_position_pct=50.0))
    engine = ExecutionEngine(
        mock_adapter, risk, store, mode=ExecutionMode.PAPER, paper_broker=PaperBroker()
    )
    decision = _decision(qty=0.5, price=100.0)
    assert decision.verdict is RiskVerdict.APPROVED
    rec = engine.submit(
        decision,
        _portfolio(),
        order_type="limit",
        intent_key="test-1",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    assert rec.state is OrderState.FILLED
    assert rec.filled_quantity > 0
    assert rec.average_fill_price is not None
    # Paper must not call real adapter create_order successfully
    mock_adapter.create_order.assert_not_called()


def test_idempotent_resubmit(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine(RiskPolicy(max_position_pct=50.0))
    engine = ExecutionEngine(mock_adapter, risk, store, mode=ExecutionMode.PAPER)
    decision = _decision(qty=0.2, price=100.0)
    r1 = engine.submit(
        decision,
        _portfolio(),
        intent_key="same-intent",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    r2 = engine.submit(
        decision,
        _portfolio(),
        intent_key="same-intent",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    assert r1.execution_id == r2.execution_id
    assert r1.client_order_id == r2.client_order_id


def test_rejected_decision_raises(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine()
    engine = ExecutionEngine(mock_adapter, risk, store, mode=ExecutionMode.PAPER)
    prop = TradeProposal(
        exchange_id="binance",
        account_id="default",
        symbol="BTC/USDT",
        side=Side.BUY,
        requested_quantity=1.0,
        requested_price=100.0,
    )
    bad = risk.evaluate(
        prop,
        _portfolio(),
        market_quality=DataQualityReport(quality=DataQuality.STALE),
    )
    assert bad.verdict is not RiskVerdict.APPROVED
    with pytest.raises(ExecutionError):
        engine.submit(bad, _portfolio(), intent_key="x")


def test_emergency_stop_blocks(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine(RiskPolicy(max_position_pct=50.0), safety_mode=SafetyMode.NORMAL)
    engine = ExecutionEngine(mock_adapter, risk, store, mode=ExecutionMode.PAPER)
    decision = _decision(qty=0.1, price=100.0)
    risk.set_safety_mode(SafetyMode.EMERGENCY_STOP)
    rec = engine.submit(
        decision,
        _portfolio(),
        intent_key="emg",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    assert rec.state is OrderState.REJECTED


def test_adapter_create_order_disabled_by_default(mock_adapter: MagicMock) -> None:
    # Real adapter path without enable stays disabled
    from crypto.core.credentials import InMemoryCredentialStore
    from crypto.exchanges.binance import BinanceAdapter

    ad = BinanceAdapter(InMemoryCredentialStore())
    assert ad.trading_enabled is False
    with pytest.raises(TradingDisabledError):
        ad.create_order("BTC/USDT", "buy", "limit", 0.01, 100.0)


def test_persistence_and_recover(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine(RiskPolicy(max_position_pct=50.0))
    engine = ExecutionEngine(mock_adapter, risk, store, mode=ExecutionMode.PAPER)
    decision = _decision(qty=0.3, price=100.0)
    rec = engine.submit(
        decision,
        _portfolio(),
        intent_key="persist-1",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    loaded = store.get(rec.execution_id)
    assert loaded is not None
    assert loaded.client_order_id == rec.client_order_id
    # recover should not explode
    engine.recover_on_startup()


def test_partial_fill_average(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine(RiskPolicy(max_position_pct=50.0))
    paper = PaperBroker(fill_ratio=0.4)
    engine = ExecutionEngine(
        mock_adapter, risk, store, mode=ExecutionMode.PAPER, paper_broker=paper
    )
    decision = _decision(qty=1.0, price=50.0)
    rec = engine.submit(
        decision,
        _portfolio(),
        intent_key="partial",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=50.0,
    )
    assert rec.state in (OrderState.PARTIALLY_FILLED, OrderState.OPEN, OrderState.FILLED)
    if rec.filled_quantity > 0:
        assert rec.average_fill_price is not None


def test_no_secret_in_audit(store: ExecutionStore, mock_adapter: MagicMock) -> None:
    risk = RiskEngine(RiskPolicy(max_position_pct=50.0))
    engine = ExecutionEngine(mock_adapter, risk, store, mode=ExecutionMode.PAPER)
    decision = _decision(qty=0.1, price=100.0)
    rec = engine.submit(
        decision,
        _portfolio(),
        intent_key="sec",
        market_quality=DataQualityReport(quality=DataQuality.COMPLETE),
        constraints=MarketConstraints(min_amount=0.001, min_cost=1.0),
        entry_price=100.0,
    )
    events = store.audit_events(rec.execution_id)
    blob = str(events).lower()
    assert "api_key" not in blob
    assert "api_secret" not in blob
    assert "authorization" not in blob
