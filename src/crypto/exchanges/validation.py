"""Validation helpers for market data.

Reject obviously corrupt values rather than silently coercing them.
"""

from __future__ import annotations

import math
from typing import Any

from crypto.exchanges.errors import MarketDataError


def require_finite(value: Any, field: str) -> float:
    """Coerce to float and reject NaN / Inf."""
    try:
        f = float(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"{field} is not a number: {value!r}") from exc
    if math.isnan(f) or math.isinf(f):
        raise MarketDataError(f"{field} is not finite: {value!r}")
    return f


def require_non_negative(value: Any, field: str) -> float:
    f = require_finite(value, field)
    if f < 0:
        raise MarketDataError(f"{field} must be non-negative: {f}")
    return f


def require_positive(value: Any, field: str) -> float:
    f = require_finite(value, field)
    if f <= 0:
        raise MarketDataError(f"{field} must be positive: {f}")
    return f


def optional_finite(value: Any, field: str) -> float | None:
    if value is None:
        return None
    return require_finite(value, field)


def optional_non_negative(value: Any, field: str) -> float | None:
    if value is None:
        return None
    return require_non_negative(value, field)


def optional_timestamp_ms(value: Any) -> int | None:
    if value is None:
        return None
    try:
        ts = int(value)
    except (TypeError, ValueError) as exc:
        raise MarketDataError(f"invalid timestamp: {value!r}") from exc
    if ts < 0:
        raise MarketDataError(f"timestamp must be non-negative: {ts}")
    return ts
