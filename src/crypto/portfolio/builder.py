"""Build PortfolioSnapshot from exchange balances and optional local positions.

Exchange balances are authoritative for free/used/total.
Positions on spot are derived from non-quote asset holdings when no
explicit position list is provided.
"""

from __future__ import annotations

from crypto.exchanges.models import AssetBalance
from crypto.market.timeutils import utc_now_ms
from crypto.portfolio.models import (
    AccountKey,
    AssetHolding,
    ExposureBreakdown,
    PortfolioSnapshot,
    Position,
    PositionSide,
)


def build_holdings(
    account: AccountKey,
    balances: list[AssetBalance] | tuple[AssetBalance, ...],
) -> tuple[AssetHolding, ...]:
    out: list[AssetHolding] = []
    for b in balances:
        free = b.free if b.free is not None else 0.0
        used = b.used if b.used is not None else 0.0
        total = b.total if b.total is not None else free + used
        if total == 0 and free == 0 and used == 0:
            continue
        out.append(
            AssetHolding(
                account=account,
                asset=b.asset.upper(),
                free=free,
                used=used,
                total=total,
            )
        )
    return tuple(out)


def compute_exposure(
    positions: tuple[Position, ...],
    holdings: tuple[AssetHolding, ...],
    *,
    quote_currency: str = "USDT",
) -> ExposureBreakdown:
    """Gross = sum |market_value|; net = sum signed market_value (LONG+, SHORT-).

    Holdings in the quote currency are not counted as exposure.
    Per-symbol / per-exchange / per-asset maps use absolute market value.
    """
    by_symbol: dict[str, float] = {}
    by_exchange: dict[str, float] = {}
    by_asset: dict[str, float] = {}
    gross = 0.0
    net = 0.0

    for p in positions:
        if p.side is PositionSide.FLAT or p.market_value is None:
            continue
        mv = p.market_value
        abs_mv = abs(mv)
        signed = mv if p.side is PositionSide.LONG else -abs_mv
        gross += abs_mv
        net += signed
        by_symbol[p.symbol] = by_symbol.get(p.symbol, 0.0) + abs_mv
        by_exchange[p.account.exchange_id] = by_exchange.get(p.account.exchange_id, 0.0) + abs_mv
        base = p.symbol.split("/")[0] if "/" in p.symbol else p.symbol
        by_asset[base] = by_asset.get(base, 0.0) + abs_mv

    return ExposureBreakdown(
        gross=gross,
        net=net,
        by_symbol=by_symbol,
        by_exchange=by_exchange,
        by_asset=by_asset,
    )


def estimate_equity(
    holdings: tuple[AssetHolding, ...],
    positions: tuple[Position, ...],
    *,
    quote_currency: str = "USDT",
    prices: dict[str, float] | None = None,
) -> tuple[float, float, float]:
    """Return (equity, available_quote, reserved_quote).

    Equity ≈ quote free+used + sum of non-quote holdings marked at price
    + unrealized from positions (if not already in holdings).
    Simple and deterministic; does not invent prices.
    """
    prices = prices or {}
    quote = quote_currency.upper()
    available = 0.0
    reserved = 0.0
    equity = 0.0

    counted_assets: set[tuple[str, str]] = set()
    for h in holdings:
        key = (h.account.exchange_id, h.asset)
        counted_assets.add(key)
        if h.asset == quote:
            available += h.free
            reserved += h.used
            equity += h.total
        else:
            px = prices.get(h.asset) or prices.get(f"{h.asset}/{quote}")
            if px is not None and px > 0:
                equity += h.total * px

    # Add unrealized from positions not already reflected
    for p in positions:
        if p.unrealized_pnl is not None:
            # Only add if we didn't mark the base via holdings
            base = p.symbol.split("/")[0] if "/" in p.symbol else p.symbol
            if (p.account.exchange_id, base) not in counted_assets and p.market_value is not None:
                equity += p.market_value

    return equity, available, reserved


def build_portfolio(
    *,
    accounts_holdings: dict[AccountKey, tuple[AssetHolding, ...]],
    positions: tuple[Position, ...] = (),
    quote_currency: str = "USDT",
    prices: dict[str, float] | None = None,
    realized_pnl: float = 0.0,
    fees: float = 0.0,
    timestamp_ms: int | None = None,
) -> PortfolioSnapshot:
    """Assemble a multi-exchange PortfolioSnapshot."""
    all_holdings: list[AssetHolding] = []
    accounts: list[AccountKey] = []
    for acct, holds in accounts_holdings.items():
        accounts.append(acct)
        all_holdings.extend(holds)

    holdings_t = tuple(all_holdings)
    equity, available, reserved = estimate_equity(
        holdings_t, positions, quote_currency=quote_currency, prices=prices
    )
    unrealized = sum(
        (p.unrealized_pnl or 0.0) for p in positions if p.side is not PositionSide.FLAT
    )
    exposure = compute_exposure(positions, holdings_t, quote_currency=quote_currency)
    ts = timestamp_ms if timestamp_ms is not None else utc_now_ms()

    return PortfolioSnapshot(
        equity=equity,
        available_balance=available,
        reserved_balance=reserved,
        holdings=holdings_t,
        positions=positions,
        unrealized_pnl=unrealized,
        realized_pnl=realized_pnl,
        fees=fees,
        exposure=exposure,
        timestamp_ms=ts,
        quote_currency=quote_currency.upper(),
        accounts=tuple(accounts),
    )


def spot_positions_from_holdings(
    account: AccountKey,
    holdings: tuple[AssetHolding, ...],
    *,
    quote_currency: str = "USDT",
    prices: dict[str, float] | None = None,
    timestamp_ms: int | None = None,
) -> tuple[Position, ...]:
    """Derive LONG spot positions from non-quote holdings (quantity > 0)."""
    prices = prices or {}
    quote = quote_currency.upper()
    ts = timestamp_ms if timestamp_ms is not None else utc_now_ms()
    positions: list[Position] = []
    for h in holdings:
        if h.asset == quote or h.total <= 0:
            continue
        symbol = f"{h.asset}/{quote}"
        px = prices.get(h.asset) or prices.get(symbol)
        mv = h.total * px if px is not None else None
        positions.append(
            Position(
                account=account,
                symbol=symbol,
                side=PositionSide.LONG,
                quantity=h.total,
                average_entry=px,
                current_price=px,
                market_value=mv,
                unrealized_pnl=None,
                realized_pnl=0.0,
                fees=0.0,
                opened_at_ms=None,
                updated_at_ms=ts,
            )
        )
    return tuple(positions)
