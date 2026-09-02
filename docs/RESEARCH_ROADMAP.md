# NVRA Research & Applied Science Roadmap

**Audit date:** 2026-09-03  
**HEAD:** `6a3efa366190ddbb16f9208dbb45d69370b1b483`  
**Scope:** read-only architecture and science audit (no production code changes).  
**Evidence basis:** ~720 Python modules, ~102 test modules under `god/`, `src/crypto/`, `tests/`.

---

## 1. Executive Summary

NVRA is a dual-engine autonomous trading *systems laboratory*: institutional agent/ML/risk stack under `god/` and exchange-oriented crypto stack under `src/crypto/`, unified by startup composition (`src/crypto/runtime/startup.py`), paper portfolio, control plane, and Windows/Linux packaging.

**Strengths (implemented with code evidence):** paper-first safety, RiskEngine + SAFE_MODE, adaptive capital risk, institutional kernel + typed evidence, ML lifecycle (calibration, drift, OOD, promotion gates), event bus with duplicate detection, resilience supervisor, chaos scenario hooks, control-plane Ed25519 license + signed offline fallback.

**Research opportunity:** treat NVRA as a **deterministic simulation + reliability + uncertainty-aware agent** lab—not as a venue to increase trading aggressiveness. Highest value work is measurable, falsifiable, local/Linux-first: replay consistency, fault injection coverage, ML calibration→risk coupling, regime-aware control, invariant formalization.

---

## 2. Conceptual Pipeline vs Reality

```
INPUT → DATA → ANALYSIS → RESEARCH → DECISION → RISK → EXECUTION → RECONCILIATION → STATE
```

| Stage | Evidence | Fidelity |
|-------|----------|----------|
| Data | `god/data`, `god/ml/dataset.py`, `god/ml/data_quality.py` | Partial–implemented |
| Analysis/ML | `god/ml/*` (regime, drift, calibration, ensemble) | Implemented (research-grade uneven) |
| Research/agents | `god/research`, `god/agent`, `god/evidence`, `god/institutional` | Partial (typed evidence; debate depth varies) |
| Decision | `god/decision` | Implemented with provenance/shadow |
| Risk | `src/crypto/risk/engine.py`, `god/risk/adaptive.py`, `god/paper/risk.py` | Implemented, dual stacks |
| Execution | paper/virtual + contract validators; LIVE gated | Paper strong; LIVE fail-closed |
| Reconciliation | startup stage + portfolio reconcile hooks | Partial |
| State | checkpoints, orchestration stores, control-plane fallback | Partial–implemented |

**Not a pure single pipeline:** dual engines (`god` vs `src/crypto`) create intentional product breadth and **research risk of contract drift**.

---

## 3. Research Priority Tiers

| Tier | Focus |
|------|--------|
| **T0** | Baseline benchmarks, invariant catalog + tests, deterministic paper replay |
| **T1** | Fault injection corpus, ML uncertainty→risk coupling, regime-aware control |
| **T2** | Performance (inference/event path), checkpoint MTTR study |
| **T3** | Formal event sourcing / CQRS evaluation, multi-agent consensus quality |
| **T4** | Live-broker field studies (never with unaudited capital) |

---

## 4. 12-Month Roadmap

| Phase | Objective | Deliverables |
|-------|-----------|--------------|
| **R0** | Baseline measurement | startup/event/risk/inference latency, memory; no code claims without numbers |
| **R1** | Deterministic simulation | fixed seed paper runs; replay hash equality |
| **R2** | Reliability | expand chaos scenarios; recovery success rates |
| **R3** | ML robustness | calibration, drift, OOD→gate metrics |
| **R4** | Risk/control | formal feedback loops; CVaR/drawdown experiments offline |
| **R5** | Execution quality | slippage/latency simulation only |
| **R6** | Autonomy | recovery ordering proofs; GUI isolation already tested |
| **R7** | Production validation | Windows+Linux matrix; control-plane E2E (separate from trading) |

Success criteria per phase: published metrics, ablation tables, no weakening of PAPER/SAFE_MODE invariants.
