# Deterministic Replay Status — Tahap 2

## Scope classification

**INTEGRATED_PARTIAL** — not synthetic-only, not full-product.

Covered: `seed → synthetic analysis → RiskEngine.evaluate → optional ExecutionStore idempotent persist → hashes`

Not covered: live feeds, full EventBus, MT5 adaptive concurrent path, GUI/broker races, process MTTR.

## R01–R10

All **PASS** in declared scope (`research/results/deterministic_replay_results.json`).

| ID | Test | Result |
|----|------|--------|
| R01 | same input + seed | PASS |
| R02 | 100 repeated runs | PASS (1 unique hash) |
| R03 | same event stream | PASS |
| R04 | reorder sensitivity | PASS |
| R05 | commutative reduce | PASS |
| R06 | fixed timestamps | PASS |
| R07 | checkpoint reload replay | PASS |
| R08 | restart same seed | PASS |
| R09 | N-run | PASS |
| R10 | artifact hash equality | PASS |
| R01b | different seed changes hash | PASS |

## Answers

1. Integrated **partial** (risk + store + synthetic analysis), not full product replay.
2. Pipeline replayable ~**61.1%** weighted.
3. Mismatch: **0** unexplained in scope.
