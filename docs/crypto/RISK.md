# Portfolio & Risk Engine

**Phase 4 — risk authority only (NO live orders)**

The Risk Engine is the final safety gate before any future execution. ML, strategy, and GUI must never bypass it.

## Architecture

```
Exchange (source of truth)
        ↓
Portfolio State (reconstruction / cache)
        ↓
Risk Engine
        ↓
RiskDecision (APPROVED | REJECTED | BLOCKED)
        ↓
Future Execution Engine (Phase 5+)
```

## Portfolio model

Multi-exchange, multi-asset:

- `AccountKey(exchange_id, account_id)` — balances are never mixed across exchanges
- `AssetHolding` — free / used / total per asset per account
- `Position` — LONG / SHORT / FLAT with quantity, entry, market value, PnL, fees
- `PortfolioSnapshot` — equity, available/reserved, holdings, positions, exposure, timestamp
- `ExposureBreakdown` — gross, net, by_symbol, by_exchange, by_asset

**Source of truth:** exchange balances, open orders, positions, and trades. Local state is a reconstruction layer for risk and recovery.

## Reconciliation

`reconcile()` compares local snapshot vs exchange balances/positions and returns:

- `matched: bool`
- typed `ReconciliationIssue` list (`balance_mismatch`, `position_mismatch`, `stale`, …)

Discrepancies are **not** silently overwritten. Risk Engine blocks new entries when reconciliation is marked unhealthy.

## Exposure

- **Gross** = Σ |market_value| of open positions  
- **Net** = Σ signed market_value (LONG positive, SHORT negative)  
- Per-symbol / per-exchange / per-asset maps use absolute values  
- Quote-currency cash is not counted as exposure  

## Risk policy

Configurable, **hardware-independent**:

| Limit | Default |
|-------|---------|
| max_position_pct | 5% equity |
| max_symbol_exposure_pct | 10% |
| max_exchange_exposure_pct | 50% |
| max_portfolio_exposure_pct | 25% |
| max_concurrent_positions | 5 |
| max_daily_loss_pct | 3% |
| max_drawdown_pct | 10% |
| max_consecutive_losses | 5 |
| default_taker_fee_pct | 0.1% |
| default_slippage_pct | 0.05% |

Hardware profile (Phase 9) may change ML complexity and cache sizes — **never** these limits.

## Position sizing

Deterministic tightest-constraint wins:

1. Stop-based risk budget (`risk_per_trade_pct` × equity / stop distance)  
2. `max_position_pct` of equity  
3. Remaining symbol / exchange / portfolio exposure headroom  
4. Available balance after fee + slippage reserve  
5. Amount precision floor  

**Never** rounds quantity up to meet exchange minimums if that would breach risk limits.

## Small-account example

```
Equity:        Rp 100.000
Available:     Rp 100.000
max_position:  5% → Rp 5.000 notional
Exchange min:  Rp 15.000

→ sized notional Rp 5.000 < min → REJECTED (ORDER_BELOW_MINIMUM)
→ NO TRADE
```

## Market data quality gate

Integrates Phase 3 `DataQualityReport`:

- INVALID / STALE / UNKNOWN → reject (configurable)  
- Never treats stale data as current  

## Circuit breakers & kill switch

`SafetyMode`:

| Mode | Effect |
|------|--------|
| NORMAL | Evaluate normally |
| WARNING | Soft state (e.g. soft data issues) |
| BLOCK_NEW_ENTRIES | Block buys |
| REDUCE_ONLY | Only risk-reducing sells |
| EMERGENCY_STOP | Block all |

Triggers include: drawdown limit, daily loss, reconciliation mismatch, exchange unavailable, abnormal move, stale/invalid data.

## Trade proposal interface

Future ML/strategy emits `TradeProposal`; Risk Engine returns `RiskDecision` with allowed quantity/notional and machine-readable `RejectReason`.

## What Phase 4 does **not** do

- Call `create_order` / `cancel_order`  
- Depend on ML libraries  
- Guarantee profit  

Trading involves substantial risk of loss.
