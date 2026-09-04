# Stage 6.1 Gap Matrix — OMS/EMS & Execution

| Area | Status | Classification |
|------|--------|----------------|
| Order state machine | PASS | PRODUCTION |
| Invalid transitions blocked | PASS | PRODUCTION |
| Risk gate (reject + EMERGENCY_STOP) | PASS | PRODUCTION |
| Idempotency / duplicate_effects=0 | PASS | PRODUCTION_PAPER |
| Partial fill | PASS | PRODUCTION_PAPER |
| ExecutionStore persistence | PASS | PRODUCTION |
| Determinism N≥20 | PASS | PRODUCTION_PAPER |
| LIVE boundary (PAPER default) | PASS | PRODUCTION |
| Real broker fill/cancel E2E | UNOBSERVABLE | Stage 10 |
| Full cancel/replace matrix | PARTIAL | existing engine support |
| Network timeout UNKNOWN path | PRODUCTION code path exists | deeper chaos later |

**Verdict:** GO-MORE-DATA until exact HEAD CI/Windows GREEN.
