# NVRA Experiment Catalog (Local / Linux-first)

All experiments: **no real capital**. Prefer synthetic data + paper/virtual execution + mocks.

## EXP-001 Deterministic paper replay
- **Hypothesis:** Same seed + same event log → identical portfolio hash.
- **Metrics:** state hash equality rate.
- **Subsystem:** paper + orchestration bus.

## EXP-002 Event-bus duplicate suppression
- **Hypothesis:** Replayed event_ids never double-apply positions.
- **Metrics:** duplicate detection rate; position count delta=0.

## EXP-003 Fault injection: broker disconnect mid-cycle
- **Hypothesis:** Runtime enters SAFE_MODE; no orphan LIVE intents.
- **Metrics:** recovery success; unsafe order count=0.
- **Tools:** mock broker, chaos scenarios.

## EXP-004 Corrupted checkpoint load
- **Hypothesis:** Corrupt JSON → fail-closed, not partial state.
- **Metrics:** exception path; SAFE_MODE flag.

## EXP-005 Stale market data gate
- **Hypothesis:** Staleness beyond threshold blocks entries.
- **Metrics:** block rate vs freshness.

## EXP-006 ML OOD → risk block
- **Hypothesis:** High OOD score increases reject probability under fixed policy.
- **Metrics:** reject rate correlation; calibration curves.

## EXP-007 Drift detector lead time
- **Hypothesis:** Drift flags appear before sustained performance drop on synthetic regime shift.
- **Metrics:** detection lag; false positive rate.

## EXP-008 Calibration impact on autonomous decisions
- **Hypothesis:** Platt/Isotonic calibration reduces overconfident entries vs raw probs.
- **Metrics:** Brier, log-loss, entry count, simulated DD.

## EXP-009 Regime label stability
- **Hypothesis:** Regime detector hysteresis reduces flip rate without large opportunity loss (sim).
- **Metrics:** transition count; PnL proxy.

## EXP-010 Adaptive risk vs fixed risk (paper)
- **Hypothesis:** CapitalAdaptiveRiskEngine reduces max DD vs fixed sizing under shock series.
- **Metrics:** max DD, time-in-market, hit rate (sim only).

## EXP-011 GUI crash isolation
- **Hypothesis:** Forced GUI exception leaves supervisor RUNNING (existing test basis).
- **Metrics:** process liveness; order side-effects=0.

## EXP-012 Control-plane offline fallback
- **Hypothesis:** Valid signed fallback → LIMITED_OFFLINE_PAPER; tamper → SAFE_MODE.
- **Metrics:** decision mode distribution (unit-level already partially covered).

## EXP-013 Promotion gate adversarial artifact
- **Hypothesis:** Bit-flip artifact bytes always reject promotion.
- **Metrics:** reject rate=100% under mutation.

## EXP-014 Startup stage failure budget
- **Hypothesis:** After N failed stage attempts, terminal SAFE_MODE; no READY leak.
- **Metrics:** terminal state distribution.

## EXP-015 Inference latency under resource profiles
- **Hypothesis:** LOW_END profile caps concurrent models as coded.
- **Metrics:** p50/p95 latency; active model count.

## EXP-016 Partial fill simulation
- **Hypothesis:** Paper/virtual engine accounting remains conserved under partial fills.
- **Metrics:** cash+position identity.

## EXP-017 Network loss heartbeat classification
- **Hypothesis:** Missed heartbeats classify CLIENT_OFFLINE not LICENSE_REVOKED.
- **Metrics:** status labels.

## EXP-018 Agent evidence incompleteness
- **Hypothesis:** Missing required evidence fields block DecisionPacket acceptance.
- **Metrics:** rejection reasons.

## EXP-019 Monte Carlo stress of drawdown limits
- **Hypothesis:** Critical DD threshold triggers paper risk halt consistently.
- **Metrics:** halt frequency vs synthetic paths.

## EXP-020 Replay after process kill
- **Hypothesis:** Kill -9 during RUNNING → restart recovers via checkpoint without duplicate orders.
- **Metrics:** INV-002/008 checks.
