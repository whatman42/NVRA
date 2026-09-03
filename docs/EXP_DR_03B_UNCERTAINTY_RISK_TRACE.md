# EXP-DR-03B — Uncertainty → Risk Composition-Root Trace

**Status:** PASS (measurement succeeded)  
**Claim CONNECTED:** **False**  
**Architecture class:** **E** disconnected `UncertaintyReport` + **C** gate-only confidence/OOD system

## Primary question

Does ML uncertainty/OOD/calibration become a control signal that changes **RiskEngine** decisions?

## Answer (evidence-based)

| Layer | Classification | Evidence |
|-------|----------------|----------|
| `evaluate_uncertainty` / `UncertaintyReport` | **DISCONNECTED** | No production callers; only tests + export |
| `MLRiskGate` + `Prediction.confidence` | **GATE-ONLY** | Filters before/at `PipelineResult`; not `RiskEngine` args |
| OOD in `pipeline.predict` | **GATE-ONLY** | Can force blocked/neutral prediction |
| Calibration | **INDIRECT** | Changes probability → upstream gates only |
| `TradeProposal` → `RiskEngine.evaluate` | **NO uncertainty fields** | Proposal has symbol/side/qty/price only |
| `AdaptiveRiskRequest` | **NO uncertainty fields** | snapshot, limits, costs — no ML uncertainty |

### Counterfactual (runtime)

- Same `TradeProposal` + portfolio, only external `UncertaintyReport` dict varies → **RiskEngine outputs identical**.
- Same probability, confidence 0.9 vs 0.1 → **MLRiskGate** `allowed` True vs False.

**H0 at RiskEngine layer: not rejected.** Uncertainty does not change RiskEngine decisions because it is not an input.

## Coverage

- uncertainty_source_count: 8
- connected_path_count: **0**
- indirect_path_count: 1
- gate_only_count: 4
- advisory_count: 2
- disconnected_count: 1

## Safety analysis

| Capability | Observed |
|------------|----------|
| Raise risk ceiling | **No** |
| Lower risk ceiling | **No** |
| Bypass RiskEngine | **No** |
| Bypass SAFE_MODE | **No** |
| Bypass reconciliation | **No** |
| Direct order influence | **No** |
| Upstream veto only | **Yes** |

No CRITICAL ML authority-increase path found.

## Minimal safe integration (PROPOSAL ONLY — not implemented)

```
UncertaintyReport
    → RiskInputAdapter (fail-closed on missing/stale/invalid)
        → optional veto / score side-channel
            → RiskEngine (immutable ceilings unchanged)
```

Constraints: ML cannot raise ceiling / authorize LIVE / bypass SAFE_MODE / reconciliation / UNKNOWN protection.

## Next experiment

EXP-DR-03C: frequency of MLRiskGate / prediction_to_proposal vetoes under synthetic streams (still no production wiring).

## Artifacts

- `research/results/uncertainty_risk_trace.json`
- `research/results/uncertainty_risk_static_graph.json`
- `research/results/uncertainty_risk_runtime_trace.json`
