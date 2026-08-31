# Execution Engine

**Phase 5 — execution + reconciliation (spot only)**

## Authority

```
TradeProposal → RiskEngine → RiskDecision → ExecutionEngine → ExchangeAdapter
```

Only `ExecutionEngine.submit(approved RiskDecision)` may place orders.  
ML, strategy, GUI, and market data **cannot** call `create_order`.

Adapter `create_order` / `cancel_order` raise `TradingDisabledError` unless  
`ExecutionEngine` temporarily enables trading for a **LIVE** submit.

## Modes

| Mode | Default | Real `create_order` |
|------|---------|---------------------|
| PAPER | Yes | Never |
| LIVE | Explicit only | Yes (gated) |

Install → PAPER → user explicitly enables LIVE → preflight → LIVE.

## State machine

```
PROPOSED → RISK_PENDING → RISK_APPROVED → SUBMITTING
    → SUBMITTED / OPEN / PARTIALLY_FILLED / FILLED
    → CANCEL_PENDING → CANCELLED
    → REJECTED | FAILED
    → UNKNOWN → RECONCILING → (resolved state)
```

Invalid transitions raise `TransitionError`. Terminal: FILLED, CANCELLED, REJECTED, FAILED.

## Idempotency

Deterministic `client_order_id` from:

`exchange|account|symbol|side|qty|price|intent_key`

Same intent → same client order id → store returns existing active/filled record. No duplicate submit.

## Crash safety

- Intent persisted to SQLite **before** venue submit (`SUBMITTING`).
- Ambiguous response → `UNKNOWN` (not FAILED + retry).
- Startup: `recover_on_startup()` loads active rows → `reconcile()` → never auto-resubmit.

## Reconciliation

Local vs exchange (or paper broker):

- missing / unexpected / status / fill mismatch  
- Exchange is authoritative for actual fills and status  
- Conflicts produce audit events; state is not silently overwritten  

## Partial fills

Weighted average fill price from fill list. Tracks filled / remaining / fees.  
Remaining-open vs cancel-remaining is policy at cancel time (explicit cancel API).

## Final risk check

```
Risk approved → prepare → FINAL RiskEngine.evaluate → submit or REJECT
```

Stale portfolio/market after first approval cannot slip through.

## Retry policy

| Situation | Action |
|-----------|--------|
| Transport failure before known accept | UNKNOWN → reconcile |
| UNKNOWN after create_order | Reconcile only — never resubmit |
| Risk rejection | No order |
| Rate limit | Bounded; no storm |

## Paper vs Live

PAPER uses `PaperBroker` with the same state machine and store.  
LIVE uses gated adapter `_do_create_order` / `_do_cancel_order` (CCXT).

## Emergency stop

`SafetyMode.EMERGENCY_STOP` → execution rejects without submit.

## Spot only

No futures, margin, leverage, or shorting in Phase 5.

## Persistence

SQLite tables: `executions`, `audit`. No API secrets stored or logged.
