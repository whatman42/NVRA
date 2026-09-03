# EXP-DR-03C.2 — Out-of-Sample Gate Robustness & Distribution Shift

**Evidence type:** EXPLORATORY SYNTHETIC — NOT MARKET VALIDATION  
**Git baseline:** `4d9ae3d`  
**Classification:** **HOLD**  
**Leakage:** **PASS**  
**Reproducibility:** **PASS**  
**Production:** UNCHANGED  
**03D:** **PREMATURE**

## Pre-registered GO bar

Δ≥0.50 with CI lo>0.30; FNR≤0.20 (regime≤0.30); FPR≤0.05 (regime≤0.10); gen gaps bounded; ≥75% regimes with Δ>0.10.

### GO flags (P3_combined)

| Flag | Pass |
|------|------|
| A Δ | false |
| B FNR | false |
| C FPR | false |
| D generalization | false |
| E robustness (win frac) | true |
| F OOD incremental | context-dependent |

## Split

TRAIN 50% / CAL 25% / TEST R0 25% of N=12000 stationary pool; R1–R7 = independent 3000-sample generators (unseen params).

## Policy freeze

Selected `min_confidence=0.5` on CALIBRATION only (max Δ among FPR≤0.05, FNR≤0.35).

## Primary TEST aggregate (bootstrap 5000 stratified)

| Metric | Point | 95% CI |
|--------|------:|--------|
| Δ | **0.431** | [0.420, 0.442] |
| FNR | **0.459** | [0.450, 0.468] |
| FPR | **0.110** | [0.105, 0.116] |

## Worst unseen regime

**R7_corr_shift** — Δ≈0.22, FNR≈0.51, FPR≈0.27

## OOD incremental

Δ(combined)−Δ(conf_only) **negative** under this synthetic OOD design → random OOD hard-veto not a free win.

## Answers

1. Confidence signal **survives OOS** (Δ>0) but below GO bar.  
2. OOD **does not** reliably improve Δ OOS here.  
3. Combined **not** better than conf-only on Δ.  
4. Threshold 0.5 is stable pick but metrics degrade vs CAL under shift.  
5. Oracle-cal arm is experimental only — not production.  
6. **FNR remains the bottleneck** (~0.46 ≫ 0.20).  
7. Catastrophic-ish: **R7_corr_shift**.  
8. Positive Δ across regimes → likely **signal**, magnitude **generator-dependent**.  
9. **03D PREMATURE** — do not open design implementation.

## Limits

Synthetic ≠ market validation. No profitability or live-safety claims.

## Artifacts

- `research/results/exp_dr_03c2_oos_gate_robustness.json`
- `research/results/exp_dr_03c2_policy_freeze.json`
