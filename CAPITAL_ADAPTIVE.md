# Capital-Adaptive Trading (NVRAFX)

## Principle

**ADAPTIVE ≠ AGGRESSIVE**

- Risk **percentage** is fixed by policy (authoritative).
- **Equity** is read from the live account snapshot before every decision.
- Position size scales with capital; risk% does **not** escalate after losses.
- Broker min/max/step constraints are authoritative.
- If the trade is not feasible under risk + constraints → **NO TRADE**.

LIVE authorization is **never** granted by this engine.

## Account state (source of truth)

Before sizing, `AccountStateEngine` validates a fresh snapshot:

- balance, equity, free margin, margin, leverage, margin level
- currency, account type, broker, server
- freshness (max age), connected flag, consistency

Stale / disconnected / invalid → **NO TRADE**.

Static config capital is **not** used as the primary risk base.

## Broker constraints

Per symbol (never hardcode in production path):

- volume_min / volume_max / volume_step
- tick_size / tick_value / contract_size
- margin requirement, trade mode, spread

Missing or invalid → **NO TRADE**.

## Formula (auditable)

```
risk_budget   = equity × risk_pct
loss_per_lot  = (stop_loss_distance / tick_size) × tick_value
raw_volume    = risk_budget / loss_per_lot
volume        = floor_to_step(raw_volume)   # ROUND DOWN only
actual_risk   = volume × loss_per_lot
```

If `volume < volume_min`:

- Compute `min_lot_risk = volume_min × loss_per_lot`
- If `min_lot_risk > risk_budget` → **NO TRADE** (never force min lot past risk)
- Else use `volume_min` only when it fits the budget

After rounding, if `actual_risk > risk_budget` → **NO TRADE**.

## Examples (risk_pct = 1%)

| Equity | Risk budget | Notes |
|--------|-------------|--------|
| $10    | $0.10       | Often **NO TRADE** if broker min lot risk ≫ budget |
| $20    | $0.20       | Same — capital floor / min lot may block |
| $32    | $0.32       | Feasible only if stop + tick geometry fit |
| $50    | $0.50       | Scales automatically after deposit |
| $100   | $1.00       | Scales automatically; still subject to constraints |

Deposit $10 → $32, withdrawal $32 → $20, profit/loss equity changes:  
**no bot reconfiguration** — refresh account snapshot and recompute.

## Capital floor

`minimum_operational_equity` (configurable). Below floor → **NO TRADE**.  
Floor is **not** a reason to raise risk%.

## Forbidden

- Martingale / double-after-loss
- Loss recovery multipliers
- Auto risk% escalation
- Raising leverage to “make min lot fit”
- Rounding **up** past risk budget
- ML / recovery / adaptive engine arming LIVE

## Integration path

```
MT5 account snapshot (fresh)
  → AccountStateEngine.validate
  → SymbolConstraints.validate
  → CapitalAdaptiveRiskEngine.evaluate
  → policy / exposure limits
  → LiveReadiness.evaluate (separate authority)
  → operator ack + explicit LIVE unlock (manual)
  → LiveExecutionController → MT5 adapter
```

## Module map

- `god/risk/account_snapshot.py` — AccountSnapshot, AccountStateEngine
- `god/risk/broker_constraints.py` — SymbolConstraints discovery/validation
- `god/risk/adaptive.py` — CapitalAdaptiveRiskEngine
- `god/risk/sizing.py` — legacy simple sizer (compatibility)
- `god/broker/mt5/adapter.py` — `symbol_constraints()` + full account fields (margin/free_margin/leverage)
- `god/broker/mt5/demo_pipeline.py` — DEMO path uses CapitalAdaptiveRiskEngine (equity-adaptive)
- `god/broker/mt5/fake.py` — `symbol_info`, `set_account_equity` for CI adaptation tests

## Tests

`tests/test_capital_adaptive.py` — capital ladder, deposit/withdrawal, broker limits, risk caps, cost, staleness, rounding, no-martingale.
