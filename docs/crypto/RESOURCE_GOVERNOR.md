# Dynamic Resource Governor

**Phase 9 — computational adaptation only**

```
ResourceGovernor  =  COMPUTATIONAL resource authority
RiskEngine        =  FINANCIAL risk authority
ExecutionEngine   =  ORDER state authority
```

The Governor **must never** modify RiskPolicy, position limits, live trading
authorization, withdrawals, or API credentials.

## Rings

| Ring | Role | Under pressure |
|------|------|----------------|
| 0 | Exchange, execution, fills, risk, kill switch | Protected capacity |
| 1 | Primary ML, ensemble, scanner | Scaled down |
| 2 | Secondary ML, prewarm, verbose analytics | Suspended |

## State machine

```
NORMAL → DEGRADED → CONSTRAINED → CRITICAL
                                      ↓
                                   RECOVERY → DEGRADED → NORMAL
```

No jump CRITICAL → NORMAL. Hysteresis via separate scale-up/down thresholds,
minimum dwell time, and recovery stability window.

## Degradation ladder

0 Normal → 2 Degraded (drop Ring 2) → 4 Constrained (minimal ML) → 6 Critical compute only.

## Stale data gate

`MarketDataFreshnessGate`: STALE / CRITICAL_STALE blocks **new strategy proposals**.
Execution/reconciliation remain independent. RiskEngine still decides financial risk.

## Integration

Consumes Phase 8 `ResourceBudget` and produces `AdaptiveBudget` for ML/scanner/caches/workers.

## Not in Phase 9

Watchdog, process restart, crash recovery (Phase 10).
