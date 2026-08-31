"""Normalize raw adapter output into MarketBar / SymbolSeries. No invention."""

from __future__ import annotations

from typing import Any, Optional

from .models import MarketBar, SymbolSeries


def normalize_bar(
    symbol: str,
    raw: dict[str, Any],
    *,
    source_id: str = "unknown",
) -> Optional[MarketBar]:
    """
    Accept flexible keys: timestamp/time/ts, close/c, open/o, high/h, low/l, volume/v.
    Missing fields remain None.
    """
    if not isinstance(raw, dict):
        return None
    ts = raw.get("timestamp") or raw.get("time") or raw.get("ts")
    if ts is not None:
        ts = str(ts)

    def _f(key: str, *alts: str) -> Optional[float]:
        for k in (key, *alts):
            if k in raw and raw[k] is not None:
                try:
                    return float(raw[k])
                except (TypeError, ValueError):
                    return None
        return None

    return MarketBar(
        symbol=symbol.upper(),
        timestamp=ts,
        open=_f("open", "o"),
        high=_f("high", "h"),
        low=_f("low", "l"),
        close=_f("close", "c"),
        volume=_f("volume", "v", "vol"),
        source_id=source_id,
        metadata={k: v for k, v in raw.items() if k not in (
            "timestamp", "time", "ts", "open", "o", "high", "h",
            "low", "l", "close", "c", "volume", "v", "vol",
        )},
    )


def normalize_series(
    symbol: str,
    raw_bars: list[dict[str, Any]] | list[MarketBar],
    *,
    source_id: str = "unknown",
    max_bars: Optional[int] = None,
) -> SymbolSeries:
    bars: list[MarketBar] = []
    for raw in raw_bars:
        if isinstance(raw, MarketBar):
            bars.append(raw)
        else:
            b = normalize_bar(symbol, raw, source_id=source_id)
            if b is not None:
                bars.append(b)
    if max_bars is not None and len(bars) > max_bars:
        bars = bars[-max_bars:]
    return SymbolSeries(
        symbol=symbol.upper(),
        bars=bars,
        source_id=source_id,
    )
