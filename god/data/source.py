"""Abstract MarketDataSource — no MT5/broker dependency."""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from .models import MarketBar


@runtime_checkable
class MarketDataSource(Protocol):
    """Fetch universe and observations. Implementations must not execute trades."""

    source_id: str

    def fetch_universe(self) -> list[str]:
        """Return deduplicated symbol list."""
        ...

    def fetch_bars(
        self,
        symbol: str,
        *,
        max_bars: Optional[int] = None,
    ) -> list[MarketBar]:
        """Return bars for symbol. Empty list if unavailable — never invent."""
        ...

    def fetch_metadata(self, symbol: str) -> dict[str, Any]:
        """Optional metadata; default empty."""
        return {}
