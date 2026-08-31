# Production Hardening & LIVE Safety (Phase 15)

## Absolute rules

- Default mode: **PAPER**
- CI: **never** places LIVE orders
- `SOFTWARE GREEN` ≠ `PRODUCTION LIVE GO`
- RiskEngine is never made more permissive
- Withdrawal default: **DISABLED**; UNKNOWN ≠ safe
- `--force-live` **cannot** bypass build hash mismatch
- TINY_CAPITAL_MODE cannot be disabled via Telegram
- No automatic capital escalation after canary success

## Authority

```
Market → ML/Scanner → Proposal → RiskEngine → ExecutionEngine → Exchange
GUI/Telegram → ControlPlane only
Governor = compute | Supervisor = recovery | RiskEngine = money
```

## ProductionGate

Critical checks include: connectivity, trading permission, withdrawal not ENABLED,
time sync, DB/model/recovery/governor/risk/control integrity, micro-capital active,
no unresolved UNKNOWN, reconciliation OK, canary round-trip, emergency-stop test,
build hash when configured.

Any critical FALSE → LIVE **NO-GO**.

## Micro-capital canary

`BUY → verify → HOLD → SELL → verify → reconcile`

Failure → SAFE MODE / block new entries. No auto-retry of ambiguous orders.

## Status after Phase 15 software delivery

| Track | Status |
|-------|--------|
| SOFTWARE | GREEN (tests pass) |
| PRODUCTION LIVE | **NOT YET VERIFIED** until operator runs real canary with GO |
