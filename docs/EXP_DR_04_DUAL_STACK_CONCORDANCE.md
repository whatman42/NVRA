# EXP-DR-04 — Dual-Stack Risk Concordance Audit

**Evidence type:** RESEARCH-ONLY · **Production:** UNCHANGED  
**Git baseline:** `44bceef`  
**Classification:** **HOLD**  
**Determinism:** **PASS**  
**D6:** **0**  
**Critical finding:** **no**  
**Real-capital readiness:** DO NOT ASSESS AS READY

## Architecture

| Stack | Surface |
|-------|---------|
| crypto | `RiskEngine.evaluate(TradeProposal, PortfolioSnapshot)` + SafetyMode + reconciliation + DataQuality |
| adaptive | `CapitalAdaptiveRiskEngine.evaluate(AdaptiveRiskRequest)` + AccountSnapshot + SymbolConstraints |
| paper | `PaperRiskEngine` simulation DD gates |
| live | `LiveAuthorizationGate` |

**No single canonical `evaluate()` shared across stacks.**

## Metrics

| Metric | Value |
|--------|------:|
| Total scenarios | 17 |
| Comparable | 8 |
| Identical decisions | 4 |
| Decision concordance | **50%** |
| Metamorphic | 10/10 |
| Taxonomy | MATCH 4, D1 4, D7 9 |
| D6 | 0 |

## Taxonomy notes

- **D1:** capital floor / risk_pct hard cap / max positions (adaptive) vs portfolio-% model (crypto)
- **D7:** SAFE_MODE, recon, stale/invalid data, exchange down — crypto-only inputs
- **D6:** none demonstrated

## Safety-critical crypto blocks

EMERGENCY_STOP, reconciliation fail, STALE, exchange unavailable → not approved (expected).

## RQ summary

Dual semantics are real and mostly intentional/non-comparable (D1/D7). Order-path ambiguity is an **architectural documentation gap**, not a proven unsafe dual-approve path in this harness. Deterministic research test is feasible.

## Classification: HOLD

Concordance 50% on small comparable set; no D6; safety metamorphic checks pass; coverage limited by API non-isomorphism.

## Remediation (separate phase — not done here)

Document authority boundaries; optional research-only adapter for fairer matrix; review qty=0 edge if undesired.

## Artifacts

- `research/results/exp_dr_04_dual_stack_concordance.json`
- `research/results/exp_dr_04_scenario_matrix.json`
- `research/results/exp_dr_04_disagreements.json`
