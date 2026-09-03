# EXP-DR-05 — Fault Injection / Chaos Recovery

**PAPER/SYNTHETIC · Production UNCHANGED · Baseline `602a29d`**  
**VERDICT: GO-MORE-DATA** · **D6: 0**

## Metrics

| Metric | Value |
|--------|------:|
| Fault scenarios | 12 |
| Runtime E4 scenarios | 12 |
| Duplicate rate | 0.0 |
| Phantom / missing order rate | 0.0 |
| Unsafe READY / execution | 0 |
| SAFE_MODE escape | 0 |
| Reconciliation bypass | 0 |
| Checkpoint corruption detection | 1.0 |
| Fallback LIVE-enable | 0 |

## Invariants

| INV | Result |
|-----|--------|
| INV-001 | UNOBSERVABLE |
| INV-002 | PASS |
| INV-004 | PASS |
| INV-008 | PASS (100/100 retries) |
| INV-010 | COMPONENT PASS + E2E UNOBSERVABLE |

## Top findings

1. `god/orchestration/models` package **missing** — orchestration CheckpointStore import broken (E2).
2. Institutional CheckpointStore **raises** on corrupt JSON (E4) — not silent accept.
3. Crypto idempotency holds under 100 synthetic retries (E4).
4. Process-level crash/MTTR **NOT OBSERVABLE** in this harness.

## Next

No CRITICAL. Prefer process-level injector design or EXP-DR-06 checkpoint depth if still open.

## Production

UNCHANGED.
