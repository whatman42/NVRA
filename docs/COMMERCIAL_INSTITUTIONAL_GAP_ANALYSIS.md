# COMM-01 — Institutional Gap Analysis

**Baseline:** EXP-DR-06 HOLD; production unchanged; orchestration models missing = separate ticket.

## Gap themes

### Critical foundation gaps (P0)
1. **Institutional checkpoint schema/version/staleness gates** — store accepts arbitrary JSON; recovery depends on callers (EXP-DR-06).
2. **Orchestration `models` package missing** — CheckpointStore import BLOCKED (engineering ticket only).
3. **Ops composition-root authority map** — path-scoped clarity exists in research; ops documentation still needed.

### Research / engine depth (P1)
4. Event-driven backtest/live parity depth vs Nautilus/LEAN.
5. L2 microstructure simulation (research sandbox).
6. INV-001 E2E LIVE precondition instrumentation (no real LIVE).
7. INV-010 fallback→ExecutionMode.LIVE E2E wiring proof.
8. Process-level fault injectors / true MTTR.

### Institutional trading stack (P2)
9. TWAP/VWAP/POV-style algos **behind** RiskEngine.
10. Multi-venue/broker connector expansion.
11. Portfolio optimization / CVaR research toolkit.
12. TCA / fill-quality analytics.

### Later / external (P3)
13. Managed GPU/cloud research farm.
14. Full desk OMS UX/blotter productization.

## Top 20 capability gaps (MISSING or weak PARTIAL)

| # | Domain | Capability | NVRA | Why it matters |
|--:|--------|------------|------|----------------|
| 1 | H | Process MTTR | MISSING | Institutional SRE bar |
| 2 | A | L2/L3 book readiness | MISSING | Microstructure realism |
| 3 | F | Execution algorithms | MISSING | Institutional execution |
| 4 | F | SOR readiness | MISSING | Multi-venue best ex |
| 5 | C | Portfolio optimization | MISSING | Portfolio construction |
| 6 | C | CVaR/ES research | MISSING | Tail risk research |
| 7 | B | Latency modeling | MISSING | Realistic sim |
| 8 | B | Market impact | MISSING | Realistic sim |
| 9 | F | Fill-quality analytics | MISSING | TCA |
| 10 | D | Liquidity risk | MISSING | Pre-trade completeness |
| 11 | A | Corporate actions | MISSING | Equity institutional |
| 12 | K | Object storage product | MISSING | Artifact scale |
| 13 | B | Event-driven BT depth | PARTIAL | Parity with Nautilus/LEAN |
| 14 | H | Checkpoint schema gates | PARTIAL | EXP-DR-06 HOLD |
| 15 | E | Cancel/replace EMS depth | PARTIAL | OMS completeness |
| 16 | F | Multi-exchange engine | PARTIAL | Venue scale |
| 17 | G | Uncertainty→risk (bounded) | PARTIAL | Still DISCONNECTED until research GO |
| 18 | J | Full multi-tenant prod | PARTIAL | Control plane templates |
| 19 | L | Alerting/monitoring product | PARTIAL | Ops maturity |
| 20 | H | Process crash injectors | PARTIAL | EXP-DR-05 gap |

## Top 10 capabilities NOT to adopt (as-is)

1. LLM/agent final execution authority — **REJECT**
2. ML auto-raising risk ceilings — **REJECT**
3. SAFE_MODE bypass for latency — **REJECT**
4. LIVE grant via offline fallback — **REJECT**
5. Orders on UNKNOWN/unreconciled state — **REJECT**
6. Silent acceptance of corrupt checkpoints — **REJECT**
7. Direct broker submit skipping RiskEngine — **REJECT**
8. Merging dual sizing engines without design — **REJECT**
9. Disabling idempotency for throughput — **REJECT**
10. “Shadow live” that can leak real orders — **REJECT**

## Architecture conflicts

- NVRA **local-first + fail-closed** vs commercial **cloud-first + convenience defaults**.
- NVRA **dual product paths** (crypto ExecutionEngine vs MT5 demo adaptive) vs single unified OMS narrative — document, don’t blur.
- Uncertainty subsystem **intentionally not** RiskEngine input until research GO (EXP-DR-03 series HOLD).
