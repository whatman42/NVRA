# Stage 5.2 Final Gap Matrix — Institutional Portfolio & Risk

## Material gates

| Gate | Status |
|------|--------|
| Portfolio state | **PASS** |
| Exposure deterministic | **PASS** |
| Sizing authority (advisory → RiskEngine) | **PASS** |
| Drawdown control | **PASS** |
| Capital/leverage fail-closed | **PASS** |
| Determinism N≥20 | **PASS** |
| Dual-stack boundary (not dual authority) | **PASS** |
| ML cannot raise ceiling (INV-003) | **PASS** |
| Invariants preserved | **PASS** |
| Production semantic regression | **NO** |
| CI / Regression / Security on `c9206a76` | **PASS** |
| Windows on `c9206a76` | see final report |

## Materiality decisions (non-blocking)

| Gap | Decision |
|-----|----------|
| Production CVaR/ES | **DEFERRED** — not required for Stage 5 minimum; research only |
| Full portfolio vol/correlation engine | **DEFERRED** — RiskEngine authority sufficient without it |
| Full multi-currency FX aggregation | **GAP / DEFERRED** — multi-exchange keys exist; no full FX book |
| Full concentration matrix | **POLICY_LIMITS** scope only |

## Authority matrix (unchanged)

```
Portfolio analytics / CapitalAdaptive sizing
        ↓ advisory only
RiskEngine (crypto)  ← final approval
        ↓
ProductionGate / SAFE_MODE / reconciliation
        ↓
ExecutionEngine
```
