"""INDODAX adapter (read-only, Phase 2).

INDODAX is an Indonesian exchange. Some endpoints and precision fields
differ from Binance; missing capabilities raise UnsupportedCapabilityError
rather than inventing behaviour.
"""

from __future__ import annotations

from crypto.exchanges.ccxt_base import CcxtReadOnlyAdapter


class IndodaxAdapter(CcxtReadOnlyAdapter):
    """INDODAX gateway via CCXT."""

    exchange_id = "indodax"
    _ccxt_exchange_id = "indodax"
    _ccxt_options: dict[str, object] = {}
