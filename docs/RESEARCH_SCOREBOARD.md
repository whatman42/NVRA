# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic hash equality |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level INVs |
| EXP-DR-03 Uncertainty→risk paths | **FAIL** | Confirmatory | connected_path_count=0 |
| EXP-DR-03B Trace | **PASS** | Confirmatory | DISCONNECTED + GATE-ONLY |
| EXP-DR-03C / 03C.1 / 03C.2 | **HOLD** | Exploratory synthetic | Gates informative; FNR bottleneck |
| EXP-DR-04 Dual-stack concordance | **HOLD** | Research audit | 50% concordance; D6=0 |
| **EXP-DR-04.1 Canonical contract** | **HOLD** | Design only | 26 concepts; authority still ambiguous |
| EXP-DR-05 Chaos recovery | INCONCLUSIVE | Exploratory | No process injectors |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Fail-closed |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |
| EXP-DR-18 Kill/restart | INCONCLUSIVE | Exploratory | Static only |

## EXP-DR-04.1 detail

| Field | Value |
|-------|-------|
| Concepts | 26 |
| E0/E1/E2/E3/E4 | 2/1/10/3/10 |
| D7 resolvable / fundamental | 7 / 2 |
| Authority ambiguity | **YES** |
| 04.2 justified | YES (research-only harness) |
| Production implementation | **NO** |

## Priority

Document dual authorities; optional EXP-DR-04.2 research concordance with contract overlays. No engine merge. No UncertaintyReport→RiskEngine. No 03D.
