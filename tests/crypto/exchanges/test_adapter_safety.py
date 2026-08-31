"""Safety invariants: no trading, secrets redacted, trading methods disabled."""

from __future__ import annotations

import logging

import pytest

from crypto.core.credentials import InMemoryCredentialStore
from crypto.core.types import SecretStr
from crypto.exchanges.binance import BinanceAdapter
from crypto.exchanges.errors import TradingDisabledError
from crypto.exchanges.factory import create_exchange_adapter, supported_exchanges
from crypto.exchanges.indodax import IndodaxAdapter
from crypto.exchanges.tokocrypto import TokocryptoAdapter


def _store_with_dummy(exchange: str = "binance") -> InMemoryCredentialStore:
    from crypto.core.credentials import ExchangeCredentials

    store = InMemoryCredentialStore()
    store.set(
        ExchangeCredentials(
            exchange_id=exchange,
            account_id="default",
            api_key=SecretStr("dummy_api_key_12345678"),
            api_secret=SecretStr("dummy_api_secret_abcdefgh"),
        )
    )
    return store


def test_supported_exchanges() -> None:
    ids = supported_exchanges()
    assert "binance" in ids
    assert "tokocrypto" in ids
    assert "indodax" in ids


def test_factory_creates_correct_types() -> None:
    store = _store_with_dummy("binance")
    assert isinstance(create_exchange_adapter("binance", store), BinanceAdapter)
    store2 = _store_with_dummy("tokocrypto")
    assert isinstance(create_exchange_adapter("tokocrypto", store2), TokocryptoAdapter)
    store3 = _store_with_dummy("indodax")
    assert isinstance(create_exchange_adapter("indodax", store3), IndodaxAdapter)


def test_factory_rejects_unknown() -> None:
    from crypto.exchanges.errors import ExchangeError

    store = InMemoryCredentialStore()
    with pytest.raises(ExchangeError, match="unsupported exchange"):
        create_exchange_adapter("not_a_real_exchange", store)


def test_create_order_disabled() -> None:
    store = _store_with_dummy()
    adapter = BinanceAdapter(store)
    with pytest.raises(TradingDisabledError, match="disabled"):
        adapter.create_order("BTC/USDT", "buy", "limit", 0.01, price=50000.0)


def test_cancel_order_disabled() -> None:
    store = _store_with_dummy()
    adapter = BinanceAdapter(store)
    with pytest.raises(TradingDisabledError, match="disabled"):
        adapter.cancel_order("order-id-123", "BTC/USDT")


def test_tokocrypto_and_indodax_also_disabled() -> None:
    for cls, eid in ((TokocryptoAdapter, "tokocrypto"), (IndodaxAdapter, "indodax")):
        store = _store_with_dummy(eid)
        adapter = cls(store)
        with pytest.raises(TradingDisabledError):
            adapter.create_order("BTC/USDT", "buy", "market", 0.01)
        with pytest.raises(TradingDisabledError):
            adapter.cancel_order("x")


def test_secret_not_in_logs(caplog: pytest.LogCaptureFixture) -> None:
    secret = SecretStr("must_not_appear_in_any_log_output_zz")
    with caplog.at_level(logging.DEBUG):
        logging.getLogger("crypto.exchanges").info("cred=%s", secret)
        logging.getLogger("crypto.exchanges").debug("repr=%r", secret)
    text = " ".join(r.message for r in caplog.records)
    assert "must_not_appear_in_any_log_output_zz" not in text
    assert "********" in text
