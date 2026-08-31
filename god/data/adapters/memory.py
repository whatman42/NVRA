"""Deterministic in-memory MarketDataSource for tests and offline use."""

from __future__ import annotations

from typing import Any, Optional

from god.data.models import MarketBar
from god.data.normalization import normalize_bar


class InMemoryMarketDataSource:
    """
    Injected store: {symbol: [bar_dict | MarketBar, ...]}.
    No network, no broker, no MT5.
    """

    def __init__(
        self,
        data: Optional[dict[str, list[Any]]] = None,
        *,
        source_id: str = "memory",
        universe: Optional[list[str]] = None,
    ) -> None:
        self.source_id = source_id
        self._data: dict[str, list[Any]] = {
            k.upper(): list(v) for k, v in (data or {}).items()
        }
        self._universe = [s.upper() for s in (universe or list(self._data.keys()))]
        # dedupe preserve order
        seen: set[str] = set()
        ordered: list[str] = []
        for s in self._universe:
            if s not in seen:
                seen.add(s)
                ordered.append(s)
        self._universe = ordered

    def fetch_universe(self) -> list[str]:
        return list(self._universe)

    def fetch_bars(
        self,
        symbol: str,
        *,
        max_bars: Optional[int] = None,
    ) -> list[MarketBar]:
        sym = symbol.upper()
        raw_list = self._data.get(sym) or []
        bars: list[MarketBar] = []
        for raw in raw_list:
            if isinstance(raw, MarketBar):
                bars.append(raw)
            elif isinstance(raw, dict):
                b = normalize_bar(sym, raw, source_id=self.source_id)
                if b is not None:
                    bars.append(b)
            elif isinstance(raw, (int, float)):
                bars.append(
                    MarketBar(
                        symbol=sym,
                        timestamp=None,
                        close=float(raw),
                        source_id=self.source_id,
                    )
                )
        if max_bars is not None and len(bars) > max_bars:
            bars = bars[-max_bars:]
        return bars

    def fetch_metadata(self, symbol: str) -> dict[str, Any]:
        return {"source_id": self.source_id, "symbol": symbol.upper()}
