"""Deterministic mock tests for CcxtReadOnlyAdapter normalisation and errors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from crypto.core.credentials import ExchangeCredentials, InMemoryCredentialStore
from crypto.core.types import SecretStr
from crypto.exchanges.binance import BinanceAdapter
from crypto.exchanges.errors import (
    AuthenticationError,
    CredentialMissingError,
    MarketDataError,
    NetworkError,
    RateLimitError,
    TradingDisabledError,
)
from crypto.exchanges.models import ConnectionHealth, PermissionStatus


def _store() -> InMemoryCredentialStore:
    s = InMemoryCredentialStore()
    s.set(
        ExchangeCredentials(
            exchange_id="binance",
            account_id="default",
            api_key=SecretStr("test_key_value_12345678"),
            api_secret=SecretStr("test_secret_value_abcdefgh"),
        )
    )
    return s


def _mock_ccxt_client(**has_flags: bool) -> MagicMock:
    client = MagicMock()
    client.has = {
        "fetchOHLCV": True,
        "fetchOpenOrders": True,
        "fetchOrder": True,
        "fetchMyTrades": True,
        "fetchPositions": False,
        "fetchStatus": True,
        "fetchTime": True,
        **has_flags,
    }
    client.symbols = ["BTC/USDT", "ETH/USDT"]
    client.markets = {
        "BTC/USDT": {
            "symbol": "BTC/USDT",
            "base": "BTC",
            "quote": "USDT",
            "active": True,
            "spot": True,
            "type": "spot",
            "precision": {"price": 2, "amount": 6},
            "limits": {
                "amount": {"min": 0.0001},
                "cost": {"min": 10.0},
            },
            "maker": 0.001,
            "taker": 0.001,
        }
    }
    client.load_markets = MagicMock(return_value=client.markets)
    client.fetch_status = MagicMock(return_value={"status": "ok"})
    client.fetch_balance = MagicMock(
        return_value={
            "free": {"BTC": 0.5, "USDT": 1000.0},
            "used": {"BTC": 0.1, "USDT": 0.0},
            "total": {"BTC": 0.6, "USDT": 1000.0},
            "info": {},
        }
    )
    client.fetch_ticker = MagicMock(
        return_value={
            "symbol": "BTC/USDT",
            "timestamp": 1_700_000_000_000,
            "bid": 42000.0,
            "ask": 42001.0,
            "last": 42000.5,
            "high": 43000.0,
            "low": 41000.0,
            "baseVolume": 100.0,
            "quoteVolume": 4_200_000.0,
        }
    )
    client.fetch_order_book = MagicMock(
        return_value={
            "symbol": "BTC/USDT",
            "timestamp": 1_700_000_000_000,
            "bids": [[42000.0, 1.5], [41999.0, 2.0]],
            "asks": [[42001.0, 1.2], [42002.0, 3.0]],
        }
    )
    client.fetch_ohlcv = MagicMock(
        return_value=[
            [1_700_000_000_000, 42000.0, 42100.0, 41900.0, 42050.0, 10.0],
            [1_700_000_060_000, 42050.0, 42200.0, 42000.0, 42100.0, 12.0],
        ]
    )
    client.fetch_open_orders = MagicMock(return_value=[])
    client.fetch_order = MagicMock(
        return_value={
            "id": "123",
            "clientOrderId": "c-1",
            "symbol": "BTC/USDT",
            "side": "buy",
            "type": "limit",
            "status": "open",
            "price": 40000.0,
            "amount": 0.01,
            "filled": 0.0,
            "remaining": 0.01,
            "timestamp": 1_700_000_000_000,
        }
    )
    client.fetch_my_trades = MagicMock(return_value=[])
    client.fetch_positions = MagicMock(return_value=[])
    return client


@pytest.fixture
def adapter_with_mock() -> BinanceAdapter:
    store = _store()
    adapter = BinanceAdapter(store)
    client = _mock_ccxt_client()
    adapter._client = client
    adapter._markets_loaded = True
    adapter._health = ConnectionHealth.CONNECTED
    return adapter


def test_missing_credential_raises() -> None:
    store = InMemoryCredentialStore()
    adapter = BinanceAdapter(store)
    with pytest.raises(CredentialMissingError):
        adapter.connect()


def test_fetch_markets_normalized(adapter_with_mock: BinanceAdapter) -> None:
    markets = adapter_with_mock.fetch_markets()
    assert len(markets) == 1
    m = markets[0]
    assert m.exchange == "binance"
    assert m.symbol == "BTC/USDT"
    assert m.base_asset == "BTC"
    assert m.quote_asset == "USDT"
    assert m.active is True
    assert m.minimum_amount == 0.0001
    assert m.maker_fee == 0.001


def test_fetch_balance_normalized(adapter_with_mock: BinanceAdapter) -> None:
    bals = adapter_with_mock.fetch_balance()
    by_asset = {b.asset: b for b in bals}
    assert "BTC" in by_asset
    assert by_asset["BTC"].free == 0.5
    assert by_asset["BTC"].used == 0.1
    assert by_asset["BTC"].total == 0.6
    assert by_asset["USDT"].free == 1000.0


def test_fetch_ticker_normalized(adapter_with_mock: BinanceAdapter) -> None:
    t = adapter_with_mock.fetch_ticker("BTC/USDT")
    assert t.symbol == "BTC/USDT"
    assert t.bid == 42000.0
    assert t.ask == 42001.0
    assert t.last == 42000.5
    assert t.volume == 100.0


def test_fetch_order_book_normalized(adapter_with_mock: BinanceAdapter) -> None:
    ob = adapter_with_mock.fetch_order_book("BTC/USDT")
    assert len(ob.bids) == 2
    assert len(ob.asks) == 2
    assert ob.bids[0].price == 42000.0
    assert ob.asks[0].price == 42001.0


def test_crossed_order_book_rejected(adapter_with_mock: BinanceAdapter) -> None:
    adapter_with_mock._client.fetch_order_book.return_value = {
        "bids": [[43000.0, 1.0]],
        "asks": [[42000.0, 1.0]],
        "timestamp": 1,
    }
    with pytest.raises(MarketDataError, match="crossed"):
        adapter_with_mock.fetch_order_book("BTC/USDT")


def test_nan_ticker_rejected(adapter_with_mock: BinanceAdapter) -> None:
    adapter_with_mock._client.fetch_ticker.return_value = {
        "symbol": "BTC/USDT",
        "last": float("nan"),
        "bid": 1.0,
        "ask": 2.0,
    }
    with pytest.raises(MarketDataError, match="not finite"):
        adapter_with_mock.fetch_ticker("BTC/USDT")


def test_negative_volume_rejected(adapter_with_mock: BinanceAdapter) -> None:
    adapter_with_mock._client.fetch_ticker.return_value = {
        "symbol": "BTC/USDT",
        "last": 1.0,
        "baseVolume": -5.0,
    }
    with pytest.raises(MarketDataError, match="non-negative"):
        adapter_with_mock.fetch_ticker("BTC/USDT")


def test_ohlcv_normalized(adapter_with_mock: BinanceAdapter) -> None:
    bars = adapter_with_mock.fetch_ohlcv("BTC/USDT", "1m")
    assert len(bars) == 2
    assert bars[0].open == 42000.0
    assert bars[1].volume == 12.0


def test_fetch_order(adapter_with_mock: BinanceAdapter) -> None:
    o = adapter_with_mock.fetch_order("123", "BTC/USDT")
    assert o.id == "123"
    assert o.side == "buy"
    assert o.amount == 0.01


def test_positions_empty_when_unsupported(adapter_with_mock: BinanceAdapter) -> None:
    positions = adapter_with_mock.fetch_positions()
    assert positions == []


def test_health_check_connected(adapter_with_mock: BinanceAdapter) -> None:
    assert adapter_with_mock.health_check() is ConnectionHealth.CONNECTED


def test_auth_error_translation(adapter_with_mock: BinanceAdapter) -> None:
    class AuthenticationErrorCcxt(Exception):
        pass

    adapter_with_mock._client.fetch_balance.side_effect = AuthenticationErrorCcxt("invalid key")
    with pytest.raises(AuthenticationError):
        adapter_with_mock.fetch_balance()


def test_rate_limit_translation(adapter_with_mock: BinanceAdapter) -> None:
    class RateLimitExceeded(Exception):
        pass

    adapter_with_mock._client.fetch_ticker.side_effect = RateLimitExceeded("too many")
    with pytest.raises(RateLimitError):
        adapter_with_mock.fetch_ticker("BTC/USDT")


def test_network_retry_then_fail(adapter_with_mock: BinanceAdapter) -> None:
    class NetworkErrorCcxt(Exception):
        pass

    adapter_with_mock._client.fetch_ticker.side_effect = NetworkErrorCcxt("timeout")
    with pytest.raises(NetworkError):
        adapter_with_mock.fetch_ticker("BTC/USDT")


def test_validate_permissions_structure(adapter_with_mock: BinanceAdapter) -> None:
    report = adapter_with_mock.validate_permissions()
    assert report.authenticated is True
    assert report.market_data is PermissionStatus.GRANTED
    assert report.account_read is PermissionStatus.GRANTED
    # trading/withdrawal unknown by default (no probe orders)
    assert report.trading is PermissionStatus.UNKNOWN
    assert report.withdrawal is PermissionStatus.UNKNOWN


def test_create_order_still_disabled_after_connect(
    adapter_with_mock: BinanceAdapter,
) -> None:
    with pytest.raises(TradingDisabledError):
        adapter_with_mock.create_order("BTC/USDT", "buy", "market", 0.01)


def test_disconnect(adapter_with_mock: BinanceAdapter) -> None:
    adapter_with_mock.disconnect()
    assert adapter_with_mock.health_check() is ConnectionHealth.DISCONNECTED


def test_connect_uses_credential_store() -> None:
    """Credentials are loaded from the store; connect path sets CONNECTED."""
    store = _store()
    adapter = BinanceAdapter(store)
    mock_instance = _mock_ccxt_client()

    def _build(self: Any, creds: Any) -> Any:
        assert creds.api_key.get_secret_value() == "test_key_value_12345678"
        assert "test_key_value_12345678" not in repr(creds)
        return mock_instance

    with patch.object(BinanceAdapter, "_build_client", _build):
        adapter.connect()

    assert adapter.health_check() is ConnectionHealth.CONNECTED
    assert adapter._markets_loaded is True
