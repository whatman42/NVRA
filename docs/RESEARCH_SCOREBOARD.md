# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| EXP-DR-03B Trace | **PASS** | Confirmatory | DISCONNECTED + GATE-ONLY |
| EXP-DR-03C Gate effectiveness | **HOLD** | Exploratory synthetic | Informative; high FNR on grid |
| **EXP-DR-03C.1 False-veto/cal** | **HOLD** | Exploratory synthetic | Pareto FNR/FPR; 0 GO candidates |
| EXP-DR-04 Dual-stack | INCONCLUSIVE | Exploratory | Non-isomorphic APIs |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | No process injectors |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | INCONCLUSIVE | Exploratory | Static only |

## EXP-DR-03C.1 detail

| Field | Value |
|-------|-------|
| Baseline FNR (combined) | 0.271 (CI ~0.25–0.29) |
| Baseline FPR | 0.018 |
| GO-bar candidates | **0** |
| conf_only Δ | 0.830 |
| combined Δ | 0.711 |
| Heavy miscal FNR | 0.787 |
| 03D | **PREMATURE** |

## Priority

Do not wire UncertaintyReport into RiskEngine. Gate research remains upstream HOLD on tradeoff characterization.
