# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| EXP-DR-03B Trace | **PASS** | Confirmatory | DISCONNECTED + GATE-ONLY |
| **EXP-DR-03C Gate effectiveness** | **HOLD** | Exploratory synthetic | Informative but high FNR |
| EXP-DR-04 Dual-stack | INCONCLUSIVE | Exploratory | Non-isomorphic APIs |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | No process injectors |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | INCONCLUSIVE | Exploratory | Static only |

## EXP-DR-03C detail

| Field | Value |
|-------|-------|
| N | 2100 |
| gate_veto_rate | 0.750 |
| delta P(allow\|good)-P(allow\|bad) | 0.351 |
| FNR / FPR | 0.538 / 0.111 |
| Counterfactual ML gate causal | true |
| Classification | **HOLD — CALIBRATION/THRESHOLD RESEARCH** |
| Market validated | **false** |
| Next | No Risk integration; optional EXP-DR-03D proposal only |

## Priority gap (unchanged)

UncertaintyReport still not a RiskEngine input. Gates are upstream HARD VETO only; improve false-veto before any side-channel design.
