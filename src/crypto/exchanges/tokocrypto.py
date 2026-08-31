"""Tokocrypto adapter (read-only, Phase 2).

Tokocrypto is Indonesia-focused. CCXT support may vary by version;
capability differences are surfaced as UnsupportedCapabilityError.
"""

from __future__ import annotations

from crypto.exchanges.ccxt_base import CcxtReadOnlyAdapter


class TokocryptoAdapter(CcxtReadOnlyAdapter):
    """Tokocrypto gateway via CCXT when available."""

    exchange_id = "tokocrypto"
    _ccxt_exchange_id = "tokocrypto"
    _ccxt_options: dict[str, object] = {}
