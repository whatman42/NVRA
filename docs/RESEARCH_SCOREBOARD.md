# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 / 03B / 03C series | **HOLD**/FAIL | Mixed | Uncertainty disconnected; gates HOLD |
| EXP-DR-04 Dual-stack concordance | **HOLD** | Research audit | 50% on 8 comparable; D6=0 |
| EXP-DR-04.1 Canonical contract | **HOLD** | Design only | 26 concepts; authority ambiguous |
| **EXP-DR-04.2 Expanded concordance** | **HOLD** | Research harness | 108 scenarios; 75.3% engine concordance |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | No process injectors |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | INCONCLUSIVE | Exploratory | Static only |

## EXP-DR-04.2 detail

| Field | Value |
|-------|-------|
| Scenarios | 108 |
| Comparable | 89 |
| Engine concordance | 75.3% |
| D1 / D7 / D6 | 22 / 19 / 0 |
| Metamorphic | 20/20 |
| Authority ambiguity | **YES** |
| Dual sizing | **YES** |
| Production implementation | **NO** |

## Priority

Document dual authorities; do not merge engines. No UncertaintyReport→RiskEngine. No 03D. Canonical contract remains research-only.
