"""Factory for exchange adapters."""

from __future__ import annotations

from crypto.core.credentials import CredentialStore
from crypto.exchanges.base import ExchangeAdapter
from crypto.exchanges.binance import BinanceAdapter
from crypto.exchanges.errors import ExchangeError
from crypto.exchanges.indodax import IndodaxAdapter
from crypto.exchanges.tokocrypto import TokocryptoAdapter

_REGISTRY: dict[str, type[ExchangeAdapter]] = {
    "binance": BinanceAdapter,
    "tokocrypto": TokocryptoAdapter,
    "indodax": IndodaxAdapter,
}


def supported_exchanges() -> list[str]:
    return sorted(_REGISTRY.keys())


def create_exchange_adapter(
    exchange_id: str,
    credential_store: CredentialStore,
    account_id: str = "default",
    *,
    sandbox: bool = False,
) -> ExchangeAdapter:
    """Create a read-only adapter for the given exchange.

    Credentials are loaded from the store on connect(); they are not
    passed as raw strings through the rest of the application.
    """
    key = exchange_id.strip().lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise ExchangeError(
            f"unsupported exchange: {exchange_id!r}. Supported: {supported_exchanges()}",
            exchange_id=exchange_id,
        )
    # All current adapters share the same constructor signature
    return cls(credential_store, account_id, sandbox=sandbox)  # type: ignore[call-arg]
