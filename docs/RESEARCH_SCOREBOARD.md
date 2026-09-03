# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| EXP-DR-03B Trace | **PASS** | Confirmatory | DISCONNECTED + GATE-ONLY |
| EXP-DR-03C Gate effectiveness | **HOLD** | Exploratory synthetic | Informative; high FNR |
| EXP-DR-03C.1 False-veto/cal | **HOLD** | Exploratory synthetic | Pareto FNR/FPR |
| EXP-DR-03C.2 OOS robustness | **HOLD** | Exploratory synthetic | Δ>0 OOS; misses GO bar |
| **EXP-DR-04 Dual-stack concordance** | **HOLD** | Research audit | 50% concordance; D6=0 |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | No process injectors |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | INCONCLUSIVE | Exploratory | Static only |

## EXP-DR-04 detail

| Field | Value |
|-------|-------|
| Comparable scenarios | 8 |
| Decision concordance | 50% |
| D6 | 0 |
| Metamorphic | 10/10 |
| Determinism | PASS |
| Real capital | DO NOT ASSESS AS READY |

## Priority

Document dual risk authorities; do not merge stacks without explicit design. No UncertaintyReport→RiskEngine. No EXP-DR-03D implementation.
