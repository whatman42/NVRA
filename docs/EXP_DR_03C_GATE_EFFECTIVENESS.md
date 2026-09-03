# EXP-DR-03C — Uncertainty Gate Effectiveness

**Design:** EXPLORATORY SYNTHETIC EVIDENCE (not market validation)  
**Git baseline:** `4b902bc`  
**Seed:** 42  
**N:** 2100  
**Classification:** **HOLD — CALIBRATION/THRESHOLD RESEARCH**

## Hypotheses

- **H0:** Gated eligibility is independent of confidence/OOD labels (gates non-informative)
- **H1:** Gated eligibility differs systematically with confidence/OOD (gates informative)
- **Practical significance:** |P(allow|good) − P(allow|bad)| ≥ 0.15

## Gate inventory

| Gate | Type | Defaults / condition | Consumer |
|------|------|----------------------|----------|
| MLRiskGate | HARD VETO | min_p=0.55, min_c=0.5 | MLPipeline.run |
| OOD check_features | HARD VETO | schema mismatch | pipeline.predict |
| evaluate_uncertainty | DISCONNECTED | — | tests only |
| Calibration | SOFT/INDIRECT | transforms p | pipeline.predict |
| Drift | ADVISORY | lifecycle | health/ops |

## Key metrics (overall)

| Metric | Value |
|--------|------:|
| gate_veto_rate | **0.750** |
| ml_gate_veto_rate | ~0.50 (conf grid) |
| ood_veto_rate | 0.50 (balanced OOD factor) |
| delta P(allow\|good)−P(allow\|bad) | **0.351** (≥ 0.15 → practically informative) |
| false_veto FNR | **0.538** |
| false_allow FPR | **0.111** |
| precision | (see JSON) |
| threshold fragile (±20% min_c) | **false** |

## Counterfactual

- Fixed p=0.70; confidence 0.9 vs 0.1 → MLRiskGate **allow vs reject** (**causal**)
- OOD schema mismatch independently vetoes

## Shift

Gates remain directionally informative under SHIFT-0/1/2 synthetic latent degradation; exact rates in `uncertainty_gate_effectiveness.json`.

## Dominance

ML conf veto and OOD veto are **not fully redundant**; both fire alone and together (matrix in JSON).

Calibration is **not** a separate hard proposal gate. Drift is **advisory only**.

## Answers

1. Veto ~**75%** of synthetic matrix cases (by design of conf/OOD grid)
2. **Yes, partially informative** (delta 0.35; causal conf gate)
3. False veto FNR ~**54%** — high cost on synthetic “good” labels
4. False allow FPR ~**11%**
5. **OOD adds** hard schema veto orthogonal to confidence
6. **Confidence adds** causal veto at MLRiskGate
7. Calibration **not redundant hard gate** — soft/indirect only
8. Drift **not hard gate** on proposal path
9. Threshold ±20%: **not fragile** under this grid
10. Integration research: **not yet** — HOLD on calibration/threshold before Risk side-channel

## Recommendation

**HOLD — CALIBRATION/THRESHOLD RESEARCH**

Do **not** implement uncertainty → RiskEngine wiring. Optional next: EXP-DR-03D **proposal only** after reducing false-veto under better labels.

## Artifacts

- `research/results/uncertainty_gate_effectiveness.json`
- `research/results/uncertainty_gate_matrix.csv`
