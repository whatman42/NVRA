# Stage 3.2 Final Gap Matrix — State / Checkpoint / Crash Recovery

## Material gates (Stage 3)

| Gate | Status | Evidence |
|------|--------|----------|
| Checkpoint semantic fail-closed | **PASS** | institutional CheckpointStore + tests |
| Corruption / stale / schema invalid → not trusted | **PASS** | stage3 matrix, unsafe_ready=0 |
| Checkpoint alone never authorizes execution | **PASS** | trusted_execution always False |
| Recovery → reconciliation → RiskEngine chain | **PASS** | production path |
| Deterministic recovery N≥20 | **PASS** | unique semantic hash = 1 |
| Idempotency (checkpoint + ExecutionStore + engine client_order_id) | **PASS** (scope A/B + component C) | duplicate_effects=0 |
| Windows NVRA.exe headless + kill/restart | **PASS** | CI HEAD cb34ac5 run 33850370520 |
| Exact HEAD CI / Regression / Security / Windows | **PASS** | all success |
| Production safety semantic regression | **NO** | harness/tests/docs only |

## Explicitly non-blocking for Stage 3 (later stages)

| Surface | Status | Assigned stage |
|---------|--------|----------------|
| GUI interactive lifecycle crash E2E | UNOBSERVABLE | Stage 9 operational/UI |
| Linux systemd service-manager E2E | UNOBSERVABLE | Stage 9 HA/ops |
| Broker/venue exactly-once (D) | OUT OF SCOPE | Stage 7/9 execution reliability |
| Product MTTR SLA | UNOBSERVABLE | Stage 9 (no invented SLA) |

## Materiality reasoning

- **GUI** is operator presentation under existing gates; authoritative recovery path is headless `NVRA.exe` (proven).
- **systemd** is deployment/HA packaging, not core checkpoint trust semantics.
- **ExecutionEngine exactly-once vs broker**: component `client_order_id` idempotent_hit exists; venue-side exactly-once requires live/sim broker and belongs to execution/ops stages.

**Stage 3 VERDICT: FULLY PASSED**
