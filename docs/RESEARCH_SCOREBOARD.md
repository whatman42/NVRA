# Research Scoreboard (Phase 0)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic pipeline hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INV-001…010 |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| EXP-DR-04 Dual-stack concordance | **INCONCLUSIVE** | Exploratory | Non-isomorphic APIs |
| EXP-DR-05 Chaos recovery | **INCONCLUSIVE** | Exploratory | Market scenarios only; N=0 faults |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed (DatabaseError) |
| EXP-DR-07 Calibration under shift | **PASS** | Exploratory | Synthetic ECE/Brier |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD strong |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject rate |
| EXP-DR-18 Kill/restart | **INCONCLUSIVE** | Exploratory | Static stages only |

## Decision gate

| Area | Decision |
|------|----------|
| Synthetic determinism | GO |
| Full product replay | GO — MORE DATA |
| Uncertainty→RiskEngine wiring | **GO** (top priority) |
| Dual-stack fixture adapter | GO — MORE DATA |
| Process chaos injectors | HOLD |
| Checkpoint integrity | GO |
| Promotion gates | GO |
| Process kill-restart | HOLD |

## Single most important research gap (evidence)

**ML uncertainty is not wired into `RiskEngine.evaluate` / `AdaptiveRiskRequest` (EXP-DR-03 FAIL, connected_path_count=0).**
