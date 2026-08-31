"""Unit tests for domain models and market-data validation."""

from __future__ import annotations

import math

import pytest

from crypto.exchanges.errors import MarketDataError
from crypto.exchanges.models import ConnectionHealth, PermissionStatus
from crypto.exchanges.validation import (
    optional_finite,
    optional_non_negative,
    require_finite,
    require_non_negative,
    require_positive,
)


def test_require_finite_rejects_nan() -> None:
    with pytest.raises(MarketDataError, match="not finite"):
        require_finite(float("nan"), "price")


def test_require_finite_rejects_inf() -> None:
    with pytest.raises(MarketDataError, match="not finite"):
        require_finite(float("inf"), "price")


def test_require_non_negative_rejects_negative() -> None:
    with pytest.raises(MarketDataError, match="non-negative"):
        require_non_negative(-1.0, "volume")


def test_require_positive_rejects_zero() -> None:
    with pytest.raises(MarketDataError, match="positive"):
        require_positive(0.0, "price")


def test_optional_helpers_accept_none() -> None:
    assert optional_finite(None, "x") is None
    assert optional_non_negative(None, "x") is None


def test_health_and_permission_enums() -> None:
    assert ConnectionHealth.CONNECTED.name == "CONNECTED"
    assert PermissionStatus.UNKNOWN.name == "UNKNOWN"
    assert math.isfinite(1.0)
