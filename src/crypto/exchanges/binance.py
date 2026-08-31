"""Binance adapter (read-only, Phase 2)."""

from __future__ import annotations

from crypto.exchanges.ccxt_base import CcxtReadOnlyAdapter


class BinanceAdapter(CcxtReadOnlyAdapter):
    """Binance spot gateway via CCXT."""

    exchange_id = "binance"
    _ccxt_exchange_id = "binance"
    _ccxt_options = {
        "options": {
            "defaultType": "spot",
        },
    }
