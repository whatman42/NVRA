"""Asset-first reachable market universe (max 1 conversion hop)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from crypto.exchanges.models import Market
from crypto.portfolio.models import AccountKey, AssetHolding


@dataclass(frozen=True, slots=True)
class ReachableMarket:
    market: Market
    account: AccountKey
    hop: int  # 0 = direct quote/base owned; 1 = one conversion
    quote_balance: float
    base_balance: float


def build_reachable_universe(
    markets: Sequence[Market],
    holdings: Sequence[AssetHolding],
    account: AccountKey,
    *,
    max_hops: int = 1,
    max_universe: int = 500,
) -> list[ReachableMarket]:
    """Return markets reachable from current holdings (0–1 hops)."""
    owned: dict[str, float] = {}
    for h in holdings:
        if h.account != account:
            continue
        if h.total > 0:
            owned[h.asset.upper()] = owned.get(h.asset.upper(), 0.0) + h.total

    if not owned:
        return []

    out: list[ReachableMarket] = []
    for m in markets:
        if not m.active:
            continue
        base = (m.base_asset or "").upper()
        quote = (m.quote_asset or "").upper()
        if not base or not quote:
            continue

        # Hop 0: own quote (can buy base) or own base (can sell)
        q_bal = owned.get(quote, 0.0)
        b_bal = owned.get(base, 0.0)
        if q_bal > 0 or b_bal > 0:
            out.append(
                ReachableMarket(
                    market=m,
                    account=account,
                    hop=0,
                    quote_balance=q_bal,
                    base_balance=b_bal,
                )
            )
            if len(out) >= max_universe:
                break
            continue

        # Hop 1: own some other asset that is quote of a bridge — simplified:
        # only allow if we own an asset that matches either side of another
        # market; Phase 7 does NOT auto multi-hop. Interface only marks hop=1
        # when quote is a common intermediate owned indirectly — skipped for
        # safety unless max_hops >= 1 and we own nothing on pair but own USDT
        # style stable used as quote elsewhere. Conservative: no auto hop-1
        # expansion beyond direct ownership unless explicitly same-account
        # asset appears as quote on this market after a single known bridge.
        # For Phase 7 we only emit hop=0 direct reachability.
        _ = max_hops  # reserved for future routing interface

    return out[:max_universe]
