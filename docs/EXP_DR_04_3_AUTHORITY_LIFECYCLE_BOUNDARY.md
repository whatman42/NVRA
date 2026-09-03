# EXP-DR-04.3 — Authority & Lifecycle Boundary Verification

**READ-ONLY research · Production UNCHANGED · Baseline `255e32b`**  
**Classification: GO-MORE-DATA**  
**D6: 0**

## Verdict

Authority is **path-scoped and largely clear**:

- **Crypto exchange path:** `RiskEngine` → `ExecutionEngine` (sole submit path); size = `allowed_quantity`; idempotent `client_order_id` in `ExecutionStore`.
- **MT5 DEMO path:** `CapitalAdaptiveRiskEngine` is **sole volume authority**; LIVE always rejected.
- These are **parallel product paths** → **dual computation**, not two owners on one execution sink.

Residual gaps: **INV-001 end-to-end UNOBSERVABLE**; **INV-010** proven at `evaluate_offline` (E2) but full wiring to block `ExecutionMode.LIVE` not E2E-traced.

## Dual sizing conclusion

**DUAL COMPUTATION across paths — NOT dual authority on one lifecycle.**

`CapitalAdaptiveRiskEngine` has **no callers under `src/crypto/` execution**; only `god/broker/mt5/demo_pipeline.py` (+ tests).

## Paper third path

- **Crypto `ExecutionMode.PAPER`:** same RiskEngine + PaperBroker (not a third risk authority).
- **god `PaperRiskEngine` / MarketDecisionEngine:** separate simulation authority (**third path**).

## SAFE_MODE / Reconciliation / Fallback / Idempotency

- SAFE_MODE: authoritative veto on crypto path + startup; no bypass found (E2/E3/E4).
- Reconciliation: startup stage + RiskEngine flag.
- Fallback: `evaluate_offline` always `live_trading=False` (E2); E2E wiring UNOBSERVABLE.
- Idempotency: crypto ExecutionStore + deterministic id **PASS E3**.

## INV summary

| INV | Status |
|-----|--------|
| INV-001 | UNOBSERVABLE E2E |
| INV-002 | PASS |
| INV-003 | PASS |
| INV-004 | PASS |
| INV-008 | PASS crypto E3 |
| INV-010 | PASS API E2; E2E UNOBSERVABLE |

## Next

Stop expanding EXP-DR-04 unless targeting INV-001 E2E research instrumentation.  
**EXP-DR-05 — Fault injection / chaos recovery** is the natural next experiment.

## Artifacts

- `research/results/exp_dr_04_3_*.json`
