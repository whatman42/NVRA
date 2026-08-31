"""UTC time helpers for market data.

All internal timestamps are milliseconds since Unix epoch in UTC.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def utc_now_ms() -> int:
    """Current UTC time as integer milliseconds."""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def ensure_utc_ms(value: Any) -> int | None:
    """Normalize various timestamp representations to UTC ms.

    Accepts:
      - int/float epoch seconds or milliseconds (heuristic)
      - datetime (naive treated as UTC)
      - None → None
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return int(value.timestamp() * 1000)
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    # Heuristic: values below 1e12 are seconds
    if n < 1_000_000_000_000:
        n = n * 1000
    return n


def is_future(ts_ms: int, *, now_ms: int | None = None, tolerance_ms: int = 60_000) -> bool:
    """True if timestamp is unreasonably in the future."""
    now = now_ms if now_ms is not None else utc_now_ms()
    return ts_ms > now + tolerance_ms


def is_stale(
    ts_ms: int | None,
    max_age_ms: int,
    *,
    now_ms: int | None = None,
) -> bool:
    """True if timestamp is older than max_age_ms or missing."""
    if ts_ms is None:
        return True
    now = now_ms if now_ms is not None else utc_now_ms()
    return (now - ts_ms) > max_age_ms


def timeframe_to_ms(timeframe: str) -> int:
    """Convert CCXT-style timeframe string to milliseconds."""
    unit = timeframe[-1]
    try:
        n = int(timeframe[:-1])
    except ValueError as exc:
        raise ValueError(f"invalid timeframe: {timeframe!r}") from exc
    if n <= 0:
        raise ValueError(f"invalid timeframe: {timeframe!r}")
    multipliers = {
        "s": 1_000,
        "m": 60_000,
        "h": 3_600_000,
        "d": 86_400_000,
        "w": 604_800_000,
    }
    if unit not in multipliers:
        raise ValueError(f"invalid timeframe unit: {timeframe!r}")
    return n * multipliers[unit]
