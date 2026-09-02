# Applied Science Gaps Catalog

Status legend: **IMPLEMENTED** | **PARTIAL** | **MISSING** | **NOT_APPLICABLE** | **SAFETY_BLOCKED**

Evidence is code/module paths, not documentation claims alone.

## A. Machine Learning

| Concept | Status | Evidence | Gap / experiment |
|---------|--------|----------|------------------|
| Calibration (Platt/Isotonic) | IMPLEMENTED | `god/ml/calibration.py` | Calibration **under shift** still research |
| Feature/pred/performance drift | IMPLEMENTED | `god/ml/drift.py` (PSI, etc.) | Lead-time metrics |
| OOD feature check | IMPLEMENTED | `god/ml/ood.py` | Multivariate density OOD |
| Uncertainty → block trade | PARTIAL | `god/ml/uncertainty.py` (`allow_trade`, HIGH_UNCERTAINTY) | Does not yet prove downstream RiskEngine coupling in all paths |
| Conformal prediction | PARTIAL | comment + prediction_set in uncertainty | Real conformal coverage guarantees MISSING |
| Ensemble uncertainty | PARTIAL | `god/ml/ensemble.py` | Variance as risk input under-specified |
| Regime detection | IMPLEMENTED | `god/ml/regime.py` | HMM/state-space MISSING |
| Online / continual learning | MISSING | — | Catastrophic forgetting controls |
| Bayesian / BMA | MISSING | — | Optional research track |
| Epistemic vs aleatoric split | MISSING | — | Research |
| Adversarial robustness suite | PARTIAL | promotion bit-flip gates in compute validation | Model-input adversaries MISSING |
| Meta / transfer learning | MISSING | — | Optional |
| Walk-forward + embargo | IMPLEMENTED | `god/ml/split.py` TimeSeriesSplitSpec.embargo | CPCV combinatorial MISSING |
| Dataset purge/embargo flags | PARTIAL | `god/ml/dataset.py` purge_embargo field | Full CPCV engine MISSING |
| Model degradation detection | PARTIAL | drift performance degradation | Formal retirement policy experiments |

## B. Time-series science

| Concept | Status | Evidence |
|---------|--------|----------|
| Expanding walk-forward | IMPLEMENTED | `god/ml/split.py` |
| Embargo gap | IMPLEMENTED | split embargo |
| Purge metadata | PARTIAL | dataset snapshot fields |
| CPCV | MISSING | — |
| Deflated Sharpe / PBO | MISSING | — |
| Block bootstrap | MISSING | — |
| HMM / Kalman | MISSING | — |
| Explicit stationarity tests | MISSING | — |
| Heteroskedasticity models | PARTIAL | regime/vol heuristics only |

## C. Uncertainty + decision science

| Concept | Status | Notes |
|---------|--------|-------|
| Confidence-aware NO_TRADE | PARTIAL | uncertainty.allow_trade |
| Uncertainty → position sizing | MISSING / research | Must not bypass risk ceilings |
| CVaR / ES optimization | MISSING | DD thresholds exist in paper risk |
| Chance constraints | MISSING | — |
| DRO / minimax | MISSING | — |
| Expected utility formal | MISSING | — |

**Key research question:** Does ML uncertainty **actually** change `RiskEngine.evaluate` outcomes on all live-adjacent paths? Spec experiments before any code change.

## D. Control theory

| Concept | Status | Evidence |
|---------|--------|----------|
| Finite state machines | IMPLEMENTED | startup stages, paper lifecycle, order states |
| Supervisory SAFE_MODE | IMPLEMENTED | RiskEngine safety_mode, autonomous SAFE_MODE |
| Hysteresis | PARTIAL | regime/risk thresholds; not proven |
| Formal stability certificates | MISSING | — |
| Recovery controller proofs | PARTIAL | supervisor + paper recovery |

SAFE_MODE as **safe absorbing state** is a strong research formalization target without changing semantics.

## E. Reliability engineering

| Concept | Status | Evidence |
|---------|--------|----------|
| Chaos scenarios | PARTIAL | `god/chaos_v7/scenarios.py` |
| RuntimeSupervisor failure map | IMPLEMENTED | `god/resilience/supervisor.py` |
| Checkpoint/restart | PARTIAL | institutional + orchestration stores |
| MTBF/MTTR measurement program | MISSING | need experiment harness |
| FTA/FMEA living docs | MISSING | research process |
| Fault coverage % | MISSING | metric program |

## F. Distributed / event systems

| Concept | Status | Evidence |
|---------|--------|----------|
| In-process event bus + dedup | IMPLEMENTED | `god/orchestration/bus.py` |
| Idempotent intents | PARTIAL–IMPLEMENTED | loop, decision, paper, production_execution |
| Full event sourcing log | MISSING | bus ≠ durable ES |
| Lamport/vector clocks | MISSING | — |
| Exactly-once end-to-end | PARTIAL | at-least-once + dedup pattern |
| Deterministic replay harness | MISSING as productized tool | research priority |
| WAL / transactional outbox | MISSING | — |

## G. Portfolio / optimization

| Concept | Status |
|---------|--------|
| Drawdown gates | IMPLEMENTED (paper) |
| Adaptive capital exposure | IMPLEMENTED (`CapitalAdaptiveRiskEngine`) |
| Mean-variance / HRP / CVaR opt | MISSING |
| Kelly sizing | MISSING (do not add live aggressiveness) |

## H. Microstructure / execution simulation

| Concept | Status | Evidence |
|---------|--------|----------|
| Paper portfolio accounting | IMPLEMENTED | `god/paper/*` |
| Partial fills / impact / queue | PARTIAL/MISSING | limited explicit microstructure models |
| Latency/rejection injection | PARTIAL | chaos / adversarial execution modules |
| Full LOB simulation | MISSING | research |

## I. Resource-aware computing

| Concept | Status | Evidence |
|---------|--------|----------|
| Hardware profiles | IMPLEMENTED | `god/institutional/resource_profiles.py` |
| Multi-objective model pick (acc×unc×lat×RAM) | PARTIAL | profiles constrain workload; full MOO MISSING |
| Quantization product path | MISSING | — |

## J. Software verification

| Concept | Status |
|---------|--------|
| Large pytest suite | IMPLEMENTED (~100 test modules) |
| Property-based (Hypothesis) | MISSING as standard |
| Mutation testing | MISSING |
| Model checking of FSM | MISSING |
| GUI fault isolation test | IMPLEMENTED |

## K. Statistical experiment design

| Concept | Status |
|---------|--------|
| Chronological splits + embargo | IMPLEMENTED |
| Dataset governance flags | PARTIAL |
| Multiple-testing correction / PBO | MISSING |
| Experiment metadata standard | MISSING (proposed in program) |
| Seed control policy | PARTIAL |
