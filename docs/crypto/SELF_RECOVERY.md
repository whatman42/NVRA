# Self-Recovery & Watchdog

**Phase 10 — crash-safe recovery without mutating risk**

## Architectural contract

| Authority | Owns |
|-----------|------|
| Supervisor / Watchdog | Failure detection & recovery |
| Resource Governor (Phase 9) | Computational load |
| Risk Engine | Financial risk limits |
| Execution Engine | Order state machine |

**TIMEOUT ≠ FAILURE. UNKNOWN ≠ FAILED. UNKNOWN ≠ SUCCESS.**

Never blind-resubmit orders. Never fabricate fills/balances.

## Heartbeat

| Class | Interval | Miss tolerance | Progress timeout |
|-------|----------|----------------|------------------|
| Critical (execution, risk) | 2s | 2 | 10s |
| Normal (exchange, MD) | 5s | 3 | 30s |
| Background (ML, scanner) | 10s | 3 | 60s |

Timers use **monotonic** clock. Diagnostic grace before UNRESPONSIVE.

## Recovery hierarchy

Level 0 observe → 1 reinit → 2 reconnect → 3 rebuild state → 4 restart worker → 5 app restart request → **SAFE MODE**.

Exponential backoff + jitter. Attempt limits per level. Circuit breaker: 5 events / 5 minutes → RECOVERY_STORM → SAFE MODE.

## SAFE MODE

Blocks new entries, ML/scanner, UNKNOWN resubmit. Keeps risk observation, reconciliation, connectivity. Does **not** change RiskPolicy. Exit only when all health gates pass.

## UNKNOWN orders

Verification schedule: 0, 2, 5, 10, 20, 30s. Resolutions: FOUND_* or **UNRESOLVED** (not FAILED). Idempotent client_order_id blocks duplicates.

## Startup

Load state → integrity_check → supervisor → connect → balances/orders (rate-limited) → reconcile → market freshness → risk → ready. Partial failure → PARTIAL / SAFE MODE. Trading blocked until ready.

## SQLite

WAL, busy_timeout, transactions, integrity_check on startup. Corruption → STORAGE recovery / SAFE MODE; never auto-delete DB.
