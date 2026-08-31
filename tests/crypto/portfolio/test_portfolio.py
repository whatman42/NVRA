"""Portfolio construction, exposure, reconciliation."""

from __future__ import annotations

import pytest

from crypto.exchanges.models import AssetBalance
from crypto.portfolio import (
    AccountKey,
    Position,
    PositionSide,
    build_holdings,
    build_portfolio,
    compute_exposure,
    reconcile,
    spot_positions_from_holdings,
)


def test_multi_exchange_holdings_not_mixed() -> None:
    binance = AccountKey("binance", "main")
    indodax = AccountKey("indodax", "main")
    h_b = build_holdings(binance, [AssetBalance("USDT", 1000.0, 0.0, 1000.0)])
    h_i = build_holdings(indodax, [AssetBalance("IDR", 100_000.0, 0.0, 100_000.0)])
    pf = build_portfolio(
        accounts_holdings={binance: h_b, indodax: h_i},
        quote_currency="USDT",
        prices={"IDR": 0.000064},
    )
    assert len(pf.accounts) == 2
    assert pf.holdings_for(binance)[0].asset == "USDT"
    assert pf.holdings_for(indodax)[0].asset == "IDR"
    # Balances stay account-scoped
    assert all(h.account in (binance, indodax) for h in pf.holdings)


def test_position_quantity_invariant() -> None:
    acct = AccountKey("binance")
    with pytest.raises(ValueError):
        Position(
            account=acct,
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            quantity=-1,
            average_entry=1.0,
            current_price=1.0,
            market_value=-1.0,
            unrealized_pnl=None,
            realized_pnl=0.0,
            fees=0.0,
            opened_at_ms=None,
            updated_at_ms=None,
        )


def test_exposure_no_double_count() -> None:
    acct = AccountKey("binance")
    positions = (
        Position(
            account=acct,
            symbol="BTC/USDT",
            side=PositionSide.LONG,
            quantity=0.1,
            average_entry=40000,
            current_price=42000,
            market_value=4200.0,
            unrealized_pnl=200.0,
            realized_pnl=0.0,
            fees=1.0,
            opened_at_ms=None,
            updated_at_ms=None,
        ),
    )
    exp = compute_exposure(positions, ())
    assert exp.gross == 4200.0
    assert exp.net == 4200.0
    assert exp.by_symbol["BTC/USDT"] == 4200.0
    assert exp.by_exchange["binance"] == 4200.0


def test_spot_positions_from_holdings() -> None:
    acct = AccountKey("binance")
    holds = build_holdings(
        acct,
        [
            AssetBalance("BTC", 0.5, 0.0, 0.5),
            AssetBalance("USDT", 1000.0, 0.0, 1000.0),
        ],
    )
    pos = spot_positions_from_holdings(acct, holds, prices={"BTC": 42000.0})
    assert len(pos) == 1
    assert pos[0].symbol == "BTC/USDT"
    assert pos[0].quantity == 0.5
    assert pos[0].market_value == 21000.0


def test_reconcile_match() -> None:
    acct = AccountKey("binance")
    bals = [AssetBalance("USDT", 500.0, 0.0, 500.0)]
    holds = build_holdings(acct, bals)
    pf = build_portfolio(accounts_holdings={acct: holds})
    result = reconcile(pf, exchange_balances={acct: bals})
    assert result.matched is True
    assert result.issues == ()


def test_reconcile_balance_mismatch() -> None:
    acct = AccountKey("binance")
    local_bals = [AssetBalance("USDT", 500.0, 0.0, 500.0)]
    exchange_bals = [AssetBalance("USDT", 400.0, 0.0, 400.0)]
    holds = build_holdings(acct, local_bals)
    pf = build_portfolio(accounts_holdings={acct: holds})
    result = reconcile(pf, exchange_balances={acct: exchange_bals})
    assert result.has_mismatch
    assert any(i.kind == "balance_mismatch" for i in result.issues)


def test_equity_from_quote() -> None:
    acct = AccountKey("binance")
    holds = build_holdings(acct, [AssetBalance("USDT", 100_000.0, 0.0, 100_000.0)])
    pf = build_portfolio(accounts_holdings={acct: holds}, quote_currency="USDT")
    assert pf.equity == 100_000.0
    assert pf.available_balance == 100_000.0
