# NVRA Deep Research Program

**Revision:** 2026-09-03  
**Code HEAD reference:** `2d03714` (research docs baseline)  
**Mode:** documentation-only; production code unchanged.  
**Safety:** no weakening of Risk Governor, SAFE_MODE, authorization, reconciliation, license, or capital gates.

## Scientific map of NVRA

| Domain | Role of NVRA | Theory in use | Partial | Missing | Evidence anchors |
|--------|--------------|---------------|---------|---------|------------------|
| A. Autonomous system | Stage machine → READY/RUNNING/SAFE_MODE | FSM, fail-closed gates | Recovery ordering proofs | Hybrid-system formalization | `god/live/autonomous_runtime.py`, `src/crypto/runtime/startup.py` |
| B. Sequential decision | Decision packets → risk → exec | Provenance, shadow, reassessment | Utility formalization | Explicit expected-utility / chance constraints | `god/decision/*` |
| C. ML system | Features → models → calibration → gates | Platt/Isotonic, PSI drift, OOD, ensemble, regime | Conformal-style stub, uncertainty report | Full conformal, Bayesian/BMA, continual learning | `god/ml/{calibration,drift,ood,uncertainty,ensemble,regime,split,dataset}.py` |
| D. Fault-tolerant stateful | Supervisor, checkpoints, journal | Checkpoint/restart, failure class mapping | Coverage metrics | FTA/FMEA as living model | `god/resilience/*`, `god/chaos_v7`, institutional checkpoint |
| E. Supervisory control | SAFE_MODE as absorbing safe state | Supervisory gating | Hysteresis design study | Lyapunov-style certificates | RiskEngine SafetyMode, paper safety |
| F. Experimental platform | Tests + paper + synthetic | Idempotency, seeds in places | Experiment metadata standard | Full research data model in CI | `tests/*`, paper stack |

## Research ladder

| Level | Scope | Allowed experiments |
|-------|-------|---------------------|
| L0 | Code/evidence audit | Static concordance, invariant inventory |
| L1 | Deterministic local | Replay hash, unit property tests |
| L2 | Synthetic faults | Chaos, corrupt checkpoint, kill-restart |
| L3 | Synthetic markets | Regime shocks, partial fills (sim) |
| L4 | Historical data | Walk-forward with purge/embargo; offline only |
| L5 | Paper trading | Long-running paper + metrics |
| L6 | Demo/sandbox broker | Connectivity; no real capital |
| L7 | Production | Ops validation; **real capital outside normal research ladder** |

## Safety-critical research proposals (DO NOT IMPLEMENT without separate review)

Any proposal that changes semantics of Risk Governor, SAFE_MODE, LIVE preconditions, UNKNOWN-state handling, license offline capability, or credential storage is **SAFETY-CRITICAL** and blocked from casual implementation.

## Commit policy for this program

Only documentation and non-production experiment harnesses under explicit approval. Default: docs-only.

## Master research map (abbreviated)

| Research ID | Domain | State | Question | Experiment | Local | Priority |
|-------------|--------|-------|----------|------------|-------|----------|
| RM-01 | Systems | PARTIAL | Deterministic replay? | EXP-DR-01 | Y | T0 |
| RM-02 | Verification | PARTIAL | INV properties? | EXP-DR-02 | Y | T0 |
| RM-03 | ML×Risk | PARTIAL | Uncertainty coupling? | EXP-DR-03 | Y | T0 |
| RM-04 | Dual-stack | UNDEFINED | Concordance? | EXP-DR-04 | Y | T1 |
| RM-05 | Reliability | PARTIAL | Chaos success CI? | EXP-DR-05 | Y | T1 |
| RM-06 | Reliability | WEAK | Corrupt checkpoint? | EXP-DR-06 | Y | T1 |
| RM-07 | ML | PARTIAL | Calibration under shift? | EXP-DR-07 | Y | T1 |
| RM-08 | Stats | PARTIAL | Embargo vs FDR? | EXP-DR-09 | Y | T2 |
| RM-09 | Control | PARTIAL | SAFE_MODE reachability? | RO-NEW-05 | Y | T1 |
| RM-10 | Execution sim | PARTIAL | Latency vs invariants? | EXP-DR-12 | Y | T2 |

Full gap tables: `APPLIED_SCIENCE_GAPS.md`. Opportunities: `RESEARCH_OPPORTUNITIES.md`.
