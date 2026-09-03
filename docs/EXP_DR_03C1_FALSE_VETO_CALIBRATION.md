# EXP-DR-03C.1 — False-Veto / Calibration Sensitivity

**Design:** EXPLORATORY SYNTHETIC EVIDENCE (not market validation)  
**Baseline:** `0be22f2` (EXP-DR-03C)  
**Seed:** 7 · **N/block:** 4000  
**Classification:** **HOLD**  
**Production changed:** false

## Pre-registered criteria

- Material FNR drop ≥ 0.10 vs baseline combined gate
- FPR rise ≤ 0.05
- Stability across synthetic regimes
- Signal must survive label & calibration stress

## RQ answers

### RQ1 — FNR/FPR vs confidence threshold

| min_confidence | FNR | FPR | Δ(good−bad) |
|----------------|-----|-----|-------------|
| 0.20 | 0.139 | 0.622 | 0.238 |
| 0.30 | 0.139 | 0.404 | 0.457 |
| 0.40 | 0.146 | 0.153 | 0.701 |
| **0.50 (baseline)** | **0.271** | **0.018** | **0.711** |
| 0.60 | 0.460 | 0.000 | 0.540 |
| 0.70 | 0.669 | 0.000 | 0.331 |
| 0.80 | 0.848 | 0.000 | 0.152 |

Lowering threshold cuts FNR but **FPR rises sharply** (Pareto tradeoff).

### RQ2 — Free lunch threshold?

**No candidate** met pre-registered GO bar (`n_candidates=0`).

### RQ3 — Stable across regimes?

**No** alternative threshold cleared the joint bar; baseline FNR worsens under shift/OOD-heavy regimes.

### RQ4 — Calibration error?

Heavy miscalibration inflates FNR to ~0.79 and collapses Δ. Oracle calibration only modestly helps (0.271→0.246). Residual false-veto is not calibration alone.

### RQ5 — Label sensitivity?

High FNR persists across strict/moderate/noisy/imbalance definitions; absolute rates move.

### RQ6 — OOD after calibration?

Schema-OOD remains meaningful for true feature failures; random synthetic OOD in combined mode can **raise FNR** vs confidence-only.

### RQ7 — Combined vs singles?

| Mode | FNR | FPR | Δ |
|------|-----|-----|---|
| none | 0.000 | 0.952 | 0.048 |
| conf_only | 0.149 | 0.020 | **0.830** |
| ood_only | 0.139 | 0.806 | 0.054 |
| combined | 0.271 | 0.018 | 0.711 |

Confidence-only dominates on Δ; combined keeps low FPR at cost of higher FNR.

Baseline FNR bootstrap CI ~0.25–0.29.

## Note vs EXP-DR-03C

03C FNR ~0.54 used a coarse conf×OOD grid. 03C.1 continuous latent model yields ~0.27 at the same API defaults. Both exploratory synthetic — not market truth.

## Classification: HOLD

Informative gates; no threshold meets material FNR↓ without FPR↑; heavy miscal hurts; 03D **PREMATURE**.

## Safety

No RiskEngine/SAFE_MODE/LIVE/ceiling changes. UncertaintyReport not integrated as RiskInput.
