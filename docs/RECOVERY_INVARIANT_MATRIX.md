# Recovery Invariant Matrix — Tahap 3

| INV | Component probe | E2E | Notes |
|-----|-----------------|-----|-------|
| INV-001 | Multi-precondition LIVE probes BLOCK | UNOBSERVABLE | fallback/unknown/unrecon/safe/auth |
| INV-002 | UNKNOWN/STALE block execution | PASS E4 | |
| INV-004 | SAFE_MODE blocks | PASS E4 | |
| INV-008 | 100 retries one effect | PASS E4 | under recovery retries |
| INV-010 | evaluate_offline live_trading=False | COMPONENT PASS | E2E UNOBSERVABLE |

## Reconciliation ordering (E2)

LICENSE_CHECK → LOAD_STATE → BROKER_CONNECT → RECONCILIATION → RISK_GOVERNOR → READY → RUNNING

READY before reconciliation: **not allowed** by stage order.
