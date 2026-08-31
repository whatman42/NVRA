from god.broker.mt5.adapter import MT5ConnectionConfig, MT5ExecutionAdapter
from god.broker.mt5.fake import FakeMetaTrader5
from god.broker.mt5.models import MT5AccountMode, MT5OrderRequest


def test_adapter_demo_connect_and_account_state():
    fake = FakeMetaTrader5(trade_mode=0)
    adapter = MT5ExecutionAdapter(MT5ConnectionConfig(allow_live_account=False), mt5_module=fake)
    assert adapter.connect()
    assert adapter.account_mode() == MT5AccountMode.DEMO
    state = adapter.account_state()
    assert state.connected
    assert state.account_type.value == "DEMO"
    assert state.equity == 10_000.0


def test_adapter_demo_order_and_idempotency():
    fake = FakeMetaTrader5(trade_mode=0)
    adapter = MT5ExecutionAdapter(MT5ConnectionConfig(allow_live_account=False), mt5_module=fake)
    assert adapter.connect()
    req = MT5OrderRequest("test-1", "EURUSD", "BUY", 0.01)
    result = adapter.submit(req)
    assert result.ok
    assert result.status == "FILLED"
    assert adapter.open_positions()
    try:
        adapter.submit(req)
        assert False, "duplicate client order id must be rejected"
    except Exception as exc:
        assert "duplicate_client_order_id" in str(exc)


def test_adapter_live_account_blocked():
    fake = FakeMetaTrader5(trade_mode=2)
    adapter = MT5ExecutionAdapter(MT5ConnectionConfig(allow_live_account=False), mt5_module=fake)
    assert adapter.connect() is False
    assert adapter.account_mode() == MT5AccountMode.UNKNOWN


def test_adapter_constraints():
    fake = FakeMetaTrader5(trade_mode=0)
    adapter = MT5ExecutionAdapter(MT5ConnectionConfig(allow_live_account=False), mt5_module=fake)
    assert adapter.connect()
    result = adapter.symbol_constraints("EURUSD")
    assert result.ok
    assert result.constraints is not None
    assert result.constraints.volume_min > 0
