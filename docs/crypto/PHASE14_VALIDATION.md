# Phase 14 — Adversarial Paper & Chaos Validation

**No LIVE orders.** Correctness > Safety > Recovery > Consistency > Speed.

## Adversarial profiles

| Profile | Intent |
|---------|--------|
| ideal | Frictionless baseline |
| retail | Realistic latency/spread/fee |
| hostile | Rejects, partials, timeouts, thin book |
| micro | Min notional / tick / step |

## Isolation

- Every execution record carries `ExecutionMode` (PAPER/LIVE).
- ML training: `assert_training_allowed` hard-blocks PAPER rows for LIVE target.

## Chaos

- Network: latency, timeout, DNS, reset, half-open + backoff.
- Market: stale/duplicate/missing + freshness gate.
- Recovery: UNKNOWN never auto-resubmit; Safe Mode blocks entries.
- Governor: Ring 0 protected; RiskPolicy unchanged under pressure.
- Notify: P0 never starved.

## Endurance

CI uses **synthetic** accelerated loops with **RSS growth slope** and queue bounds.
Wall-clock 72h is an operational runbook target, not a CI block.

## Acceptance

`tests/integration/test_acceptance.py` exercises the authority chain in PAPER only.
