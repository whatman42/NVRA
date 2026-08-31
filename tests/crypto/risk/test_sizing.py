"""Position sizing edge cases including small accounts."""

from __future__ import annotations

from crypto.risk.models import MarketConstraints
from crypto.risk.policy import RiskPolicy
from crypto.risk.sizing import compute_position_size, meets_exchange_minimums


def test_normal_sizing() -> None:
    r = compute_position_size(
        equity=10_000.0,
        available_balance=10_000.0,
        entry_price=100.0,
        policy=RiskPolicy(max_position_pct=5.0),
    )
    assert r.max_notional == pytest_approx(500.0, rel=0.02)
    assert r.max_quantity > 0


def pytest_approx(val: float, rel: float = 0.01) -> float:
    # tiny helper to avoid importing pytest in assert expression complexity
    return val  # simplified — use real pytest.approx in asserts below


def test_sizing_with_pytest_approx() -> None:
    import pytest

    r = compute_position_size(
        equity=10_000.0,
        available_balance=10_000.0,
        entry_price=100.0,
        policy=RiskPolicy(max_position_pct=5.0),
    )
    assert r.max_notional == pytest.approx(500.0, rel=0.02)


def test_small_account_rp100k() -> None:
    """Equity Rp100_000; 5% = 5000; exchange min cost 15000 → below minimum."""
    import pytest

    policy = RiskPolicy(max_position_pct=5.0)
    r = compute_position_size(
        equity=100_000.0,
        available_balance=100_000.0,
        entry_price=1_000.0,
        policy=policy,
    )
    # 5% of 100k = 5000 notional
    assert r.max_notional == pytest.approx(5000.0, rel=0.05)
    constraints = MarketConstraints(min_cost=15_000.0, min_amount=0.01)
    assert meets_exchange_minimums(r.max_quantity, 1_000.0, constraints) is False


def test_zero_balance() -> None:
    r = compute_position_size(
        equity=0.0,
        available_balance=0.0,
        entry_price=100.0,
        policy=RiskPolicy(),
    )
    assert r.max_quantity == 0.0
    assert r.max_notional == 0.0


def test_insufficient_balance_limits() -> None:

    r = compute_position_size(
        equity=10_000.0,
        available_balance=50.0,
        entry_price=100.0,
        policy=RiskPolicy(max_position_pct=50.0),
    )
    assert r.max_notional <= 50.0 * 1.01  # fees reserve
    assert r.limited_by == "available_balance"


def test_exposure_headroom() -> None:
    import pytest

    r = compute_position_size(
        equity=10_000.0,
        available_balance=10_000.0,
        entry_price=100.0,
        policy=RiskPolicy(max_position_pct=50.0, max_symbol_exposure_pct=10.0),
        existing_symbol_exposure=900.0,  # 9% already
    )
    # headroom ~1% = 100
    assert r.max_notional == pytest.approx(100.0, rel=0.05)


def test_precision_floor() -> None:
    r = compute_position_size(
        equity=10_000.0,
        available_balance=10_000.0,
        entry_price=3.0,
        policy=RiskPolicy(max_position_pct=5.0),
        constraints=MarketConstraints(amount_precision=2),
    )
    # quantity should have at most 2 decimal places
    assert r.max_quantity == round(r.max_quantity, 2)
