# Research Scoreboard (Phase 0–1)

| Experiment | Status | Design | Notes |
|------------|--------|--------|-------|
| EXP-DR-01 Deterministic replay | **PASS** | Confirmatory | Synthetic |
| EXP-DR-02 Invariant probes | **PASS** | Exploratory | API-level |
| EXP-DR-03 series | HOLD/FAIL | Mixed | Uncertainty disconnected |
| EXP-DR-04 series | HOLD → **GO-MORE-DATA** | Research | Path-scoped authority |
| **EXP-DR-05 Fault/chaos recovery** | **GO-MORE-DATA** | E4 harness | No unsafe recovery; process MTTR N/O |
| EXP-DR-06 Checkpoint corruption | **PASS** | Confirmatory | Prior; institutional raises on corrupt |
| EXP-DR-07 Calibration shift | **PASS** | Exploratory | Synthetic |
| EXP-DR-08 OOD vs confidence | **PASS** | Exploratory | Schema OOD |
| EXP-DR-14 Promotion mutation | **PASS** | Confirmatory | 100% reject |

## EXP-DR-05 detail

| Field | Value |
|-------|-------|
| Verdict | **GO-MORE-DATA** |
| Duplicate rate | 0 |
| Unsafe execution | 0 |
| INV-008 | PASS |
| INV-001 | UNOBSERVABLE |
| Process MTTR | NOT OBSERVABLE |
| Production | UNCHANGED |
| Finding | orchestration/models package missing |
