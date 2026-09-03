# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 series | HOLD/FAIL | Mixed | Uncertainty disconnected |
| EXP-DR-04 Dual-stack | **HOLD** | Research audit | 50% on 8 comparable |
| EXP-DR-04.1 Canonical contract | **HOLD** | Design only | Authority ambiguous |
| EXP-DR-04.2 Expanded concordance | **HOLD** | Research harness | 75.3% engine concordance |
| **EXP-DR-04.3 Authority/lifecycle** | **GO-MORE-DATA** | Read-only trace | Path-scoped authority; dual computation |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | Recommended next |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |

## EXP-DR-04.3 detail

| Field | Value |
|-------|-------|
| Classification | **GO-MORE-DATA** |
| D6 | 0 |
| Dual sizing | DUAL_COMPUTATION (path-scoped) |
| INV-001 | UNOBSERVABLE E2E |
| INV-008 | PASS crypto E3 |
| INV-010 | PASS evaluate_offline E2 |
| Production | UNCHANGED |
| Next | EXP-DR-05 |
