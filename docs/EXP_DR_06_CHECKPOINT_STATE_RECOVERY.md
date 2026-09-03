# EXP-DR-06 — Corrupted Checkpoint & State Recovery Depth

**PAPER/SYNTHETIC · Production UNCHANGED · Baseline `2086d7a`**  
**VERDICT: HOLD** · **D6: 0** · **Seed: 19**

## Inventory

| Store | Status |
|-------|--------|
| Institutional SQLite | USABLE — no schema/hash |
| CycleCheckpointStore | USABLE — content_hash |
| Orchestration CheckpointStore | **BLOCKED** (models package missing) |
| ExecutionStore | USABLE — idempotency |
| Startup LOAD_STATE | PARTIAL |

## Metrics

| Metric | Value |
|--------|------:|
| Corruption scenarios | 22 |
| Silent corruption acceptance | **0** |
| Unsafe READY | 0 |
| Unsafe execution | 0 |
| UNKNOWN → execution | 0 |
| SAFE_MODE escape | 0 |
| Reconciliation bypass | 0 |
| Duplicate effects | 0 |

## Invariants

| INV | Result |
|-----|--------|
| INV-002 | PASS |
| INV-004 | PASS |
| INV-008 | PASS |
| INV-010 | COMPONENT PASS + E2E UNOBSERVABLE |

Process MTTR: **NOT OBSERVABLE**

## Top findings

1. Orchestration models still missing — **not repaired** in this experiment.
2. Institutional store accepts arbitrary JSON (no version/sequence/staleness gate).
3. Corrupt JSON fails closed via exception; cycle store returns CORRUPTED on hash mismatch.
4. Research recovery policy blocks UNKNOWN / SAFE_MODE / READY-without-recon from execution.

## Residual gaps

1. Production schema validation for institutional checkpoints
2. Orchestration checkpoint path (separate ticket)
3. Process MTTR / INV-001 E2E

## Production

UNCHANGED. No production fix applied.
