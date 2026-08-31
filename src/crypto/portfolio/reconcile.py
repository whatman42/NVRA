"""Reconciliation: local portfolio state vs exchange state.

Never silently overwrites discrepancies. Returns a typed result.
"""

from __future__ import annotations

from crypto.exchanges.models import AssetBalance
from crypto.market.timeutils import utc_now_ms
from crypto.portfolio.builder import build_holdings
from crypto.portfolio.models import (
    AccountKey,
    PortfolioSnapshot,
    Position,
    ReconciliationIssue,
    ReconciliationResult,
)


def reconcile_balances(
    account: AccountKey,
    local: PortfolioSnapshot,
    exchange_balances: list[AssetBalance] | tuple[AssetBalance, ...],
    *,
    tolerance: float = 1e-8,
) -> list[ReconciliationIssue]:
    """Compare local holdings for an account against exchange balances."""
    issues: list[ReconciliationIssue] = []
    exchange_holdings = {h.asset: h for h in build_holdings(account, exchange_balances)}
    local_holdings = {h.asset: h for h in local.holdings_for(account)}

    all_assets = set(exchange_holdings) | set(local_holdings)
    for asset in sorted(all_assets):
        loc = local_holdings.get(asset)
        exc = exchange_holdings.get(asset)
        loc_total = loc.total if loc else 0.0
        exc_total = exc.total if exc else 0.0
        if abs(loc_total - exc_total) > tolerance:
            issues.append(
                ReconciliationIssue(
                    kind="balance_mismatch",
                    account=account,
                    detail=f"asset={asset}",
                    local_value=loc_total,
                    exchange_value=exc_total,
                )
            )
    return issues


def reconcile_positions(
    account: AccountKey,
    local_positions: tuple[Position, ...],
    exchange_positions: tuple[Position, ...],
    *,
    tolerance: float = 1e-8,
) -> list[ReconciliationIssue]:
    """Compare positions by symbol for one account."""
    issues: list[ReconciliationIssue] = []
    local_map = {p.symbol: p for p in local_positions if p.account == account}
    exchange_map = {p.symbol: p for p in exchange_positions if p.account == account}
    all_symbols = set(local_map) | set(exchange_map)
    for sym in sorted(all_symbols):
        lp = local_map.get(sym)
        ep = exchange_map.get(sym)
        lq = lp.quantity if lp else 0.0
        eq = ep.quantity if ep else 0.0
        if abs(lq - eq) > tolerance:
            issues.append(
                ReconciliationIssue(
                    kind="position_mismatch",
                    account=account,
                    detail=f"symbol={sym}",
                    local_value=lq,
                    exchange_value=eq,
                )
            )
    return issues


def reconcile(
    local: PortfolioSnapshot,
    *,
    exchange_balances: dict[AccountKey, list[AssetBalance] | tuple[AssetBalance, ...]],
    exchange_positions: dict[AccountKey, tuple[Position, ...]] | None = None,
    tolerance: float = 1e-8,
    max_local_age_ms: int | None = None,
    now_ms: int | None = None,
) -> ReconciliationResult:
    """Full reconciliation across provided accounts.

    Does not mutate local state. Caller decides how to act on issues.
    """
    now = now_ms if now_ms is not None else utc_now_ms()
    issues: list[ReconciliationIssue] = []

    if max_local_age_ms is not None:
        age = now - local.timestamp_ms
        if age > max_local_age_ms:
            for acct in local.accounts:
                issues.append(
                    ReconciliationIssue(
                        kind="stale",
                        account=acct,
                        detail=f"local snapshot age_ms={age}",
                        local_value=float(local.timestamp_ms),
                        exchange_value=float(now),
                    )
                )

    for account, bals in exchange_balances.items():
        issues.extend(reconcile_balances(account, local, bals, tolerance=tolerance))
        if exchange_positions and account in exchange_positions:
            issues.extend(
                reconcile_positions(
                    account,
                    local.positions,
                    exchange_positions[account],
                    tolerance=tolerance,
                )
            )

    return ReconciliationResult(
        matched=len(issues) == 0,
        issues=tuple(issues),
        checked_at_ms=now,
    )
