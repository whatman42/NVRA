"""Normalized symbol representation.

Consumers use NormalizedSymbol; exchange-native strings are preserved
for diagnostics only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_PAIR_RE = re.compile(r"^([A-Za-z0-9]+)[/_-]?([A-Za-z0-9]+)$")


@dataclass(frozen=True, slots=True)
class NormalizedSymbol:
    """Exchange-agnostic trading pair.

    Internal form is always BASE/QUOTE uppercase, e.g. BTC/USDT, ETH/IDR.
    """

    base: str
    quote: str
    exchange_id: str
    native: str  # original exchange symbol for diagnostics

    @property
    def symbol(self) -> str:
        return f"{self.base}/{self.quote}"

    def __str__(self) -> str:
        return self.symbol


def normalize_symbol(
    exchange_id: str,
    native: str,
    *,
    base: str | None = None,
    quote: str | None = None,
) -> NormalizedSymbol:
    """Build a NormalizedSymbol from native string and optional base/quote.

    If base/quote are provided (from market metadata), they take precedence.
    Otherwise the native string is parsed with common separators.
    """
    if base and quote:
        return NormalizedSymbol(
            base=base.upper(),
            quote=quote.upper(),
            exchange_id=exchange_id,
            native=native,
        )

    cleaned = native.strip().upper().replace("-", "/").replace("_", "/")
    if "/" in cleaned:
        parts = cleaned.split("/")
        if len(parts) == 2 and parts[0] and parts[1]:
            return NormalizedSymbol(
                base=parts[0],
                quote=parts[1],
                exchange_id=exchange_id,
                native=native,
            )

    m = _PAIR_RE.match(native.strip())
    if m:
        return NormalizedSymbol(
            base=m.group(1).upper(),
            quote=m.group(2).upper(),
            exchange_id=exchange_id,
            native=native,
        )

    raise ValueError(f"cannot normalize symbol {native!r} on {exchange_id}")
