# Research Opportunities (Unknown-Unknown + Extensions)

Opportunities **not** merely restating the first roadmap list. IDs **RO-NEW-***.

| ID | Domain | Research question | Why NVRA | Current | Missing | Hypotheses / metrics | Safety | Local |
|----|--------|-------------------|----------|---------|---------|----------------------|--------|-------|
| RO-NEW-01 | ML×Risk | Does `UncertaintyReport.allow_trade=False` change RiskEngine rejects on all decision paths? | Dual path risk of bypass | uncertainty.py + RiskEngine | Path coverage map | Path coverage ≥95%; reject delta | Low | Yes |
| RO-NEW-02 | Verification | Can INV-001–004 be encoded as property tests? | Safety core | docs invariants | Hypothesis tests | Property pass rate | Low | Yes |
| RO-NEW-03 | Systems | What minimal event log schema enables hash-stable replay? | Bus only | EventBus | Durable log + reducer | Replay equality | Low | Yes |
| RO-NEW-04 | Stats | Does embargo width change false discovery of weak signals? | split embargo exists | split.py | Sweep study | FDR vs embargo | Low | Yes |
| RO-NEW-05 | Control | Is SAFE_MODE reachable from every fault class within N steps? | Supervisor map | resilience | Exhaustive graph | Reachability | Low | Yes |
| RO-NEW-06 | Dual-stack | Do crypto RiskEngine and paper/adaptive risk agree on blocked reasons for isomorphic inputs? | Dual engines | both stacks | Concordance matrix | Disagreement rate | Low | Yes |
| RO-NEW-07 | Reliability | What is empirical recovery success by fault class under chaos_v7? | scenarios module | partial | Coverage metrics | Success rate CI | Low | Yes |
| RO-NEW-08 | ML | Do prediction-set widths from uncertainty correlate with realized error? | prediction_set field | partial conformal | Real coverage | Coverage vs nominal | Low | Yes |
| RO-NEW-09 | Resources | Under LOW_END profile, does forced model shed preserve risk rejects? | resource profiles | implemented profiles | Stress harness | Reject invariance | Low | Yes |
| RO-NEW-10 | Execution sim | Does introducing synthetic latency change paper PnL distribution shape only, not risk invariant? | paper stack | limited micro | Latency injector | INV hold; KS on PnL | Low | Yes |
| RO-NEW-11 | Decision | Does shadow decision stream diverge from primary under drift injection? | decision/shadow.py | implemented | Drift coupling | Divergence rate | Low | Yes |
| RO-NEW-12 | Governance | Can promotion reject rate under artifact mutation stay 100% across model formats? | compute validation | gates | Format matrix | Reject=100% | Low | Yes |

**Novelty language (no literature search claimed):** POTENTIALLY NOVEL for dual-stack concordance method and uncertainty-path coverage; POSSIBLY KNOWN for conformal/replay/chaos metrics; LIKELY ESTABLISHED for walk-forward embargo hygiene.

## Classification

| Gap | Class |
|-----|-------|
| Event log + replay harness | SCIENCE + ENGINEERING |
| Uncertainty path coverage | SCIENCE + ENGINEERING |
| Property tests for invariants | ENGINEERING (+ verification science) |
| CPCV / PBO | SCIENCE |
| CVaR optimizer | SCIENCE (sim only) |
| Faster cache alone | ENGINEERING / NOT A REAL SCIENCE GAP |
| Weakening SAFE_MODE for “research” | SAFETY_BLOCKED |
