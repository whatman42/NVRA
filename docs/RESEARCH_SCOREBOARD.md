# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| EXP-DR-03B Trace | **PASS** | Confirmatory | DISCONNECTED + GATE-ONLY |
| EXP-DR-03C Gate effectiveness | **HOLD** | Exploratory synthetic | Informative; high FNR |
| EXP-DR-03C.1 False-veto/cal | **HOLD** | Exploratory synthetic | Pareto FNR/FPR; 0 GO candidates |
| **EXP-DR-03C.2 OOS robustness** | **HOLD** | Exploratory synthetic | Δ>0 OOS; FNR/FPR miss GO bar |
| EXP-DR-04 Dual-stack | INCONCLUSIVE | Exploratory | Non-isomorphic APIs |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | No process injectors |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | INCONCLUSIVE | Exploratory | Static only |

## EXP-DR-03C.2 detail

| Field | Value |
|-------|-------|
| Leakage | PASS |
| Reproducibility | PASS |
| Primary Δ | 0.431 [0.420, 0.442] |
| FNR | 0.459 [0.450, 0.468] |
| FPR | 0.110 [0.105, 0.116] |
| Worst regime | R7_corr_shift |
| 03D | **PREMATURE** |
| Integration | **DO NOT IMPLEMENT** |

## Priority

Upstream gates remain research-HOLD. No UncertaintyReport→RiskEngine wiring.
