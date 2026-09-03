# Research Scoreboard (Phase 0 + Phase 1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic pipeline hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INV-001…010 |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| **EXP-DR-03B Trace** | **PASS** | Confirmatory | DISCONNECTED+GATE-ONLY proven |
| EXP-DR-04 Dual-stack concordance | **INCONCLUSIVE** | Exploratory | Non-isomorphic APIs |
| EXP-DR-05 Chaos recovery | **INCONCLUSIVE** | Exploratory | Market scenarios only |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration under shift | **PASS** | Exploratory | Synthetic ECE/Brier |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | **INCONCLUSIVE** | Exploratory | Static stages only |

## EXP-DR-03B detail

| Field | Value |
|-------|-------|
| CONNECTED claim | **False** |
| Classification | DISCONNECTED (`UncertaintyReport`) + GATE-ONLY (`MLRiskGate`/OOD/confidence) |
| RiskEngine counterfactual | Identical outputs when only uncertainty dict changes |
| Safety critical path | **None** |
| Next | EXP-DR-03C optional; integration = proposal only |

## Single most important research gap (still)

**`UncertaintyReport` is not an input to `RiskEngine.evaluate`.** Pre-proposal gates exist separately.
