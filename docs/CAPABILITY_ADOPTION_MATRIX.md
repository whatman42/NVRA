# COMM-01 — Capability Adoption Matrix

Legend: **A** ADOPT NOW · **B** ADOPT AFTER RESEARCH · **C** ADAPT TO NVRA · **D** ALREADY COVERED · **E** NOT WORTH · **F** EXTERNAL ONLY · **G** REJECT (safety/governance)

| Capability | Class | Rationale |
|------------|-------|-----------|
| Checkpoint schema/version/staleness | C | EXP-DR-06; strengthens fail-closed |
| Orchestration models package | A | Eng ticket; restore import |
| Composition-root authority runbook | C | EXP-DR-04.3 residual |
| Event-driven BT/live parity depth | B | Nautilus/LEAN-class; keep risk gate |
| L2 microstructure sim | B | Research sandbox only |
| INV-001 E2E instrumentation | C | Research-only |
| INV-010 E2E wiring proof | C | Research-only |
| Process fault injectors | B | EXP-DR-05 gap |
| TWAP/VWAP/POV behind RiskEngine | B | Never bypass risk |
| Multi-broker connectors | F/C | Prefer adapters |
| Portfolio opt / CVaR toolkit | B | Research layer |
| TCA / fill quality | B | Analytics only |
| Managed GPU cloud | F | External providers exist |
| Desk OMS full UX | B | Large surface |
| Data quality veto | D | SUPERIOR |
| Idempotent client orders | D | INV-008 |
| SAFE_MODE / recon gates | D | EXISTS |
| Scientific evidence packages | D | SUPERIOR |
| Agent final authority | G | Safety |
| ML ceiling raise | G | INV-003 |
| Fallback LIVE | G | INV-010 |
| Skip RiskEngine submit | G | Architecture |
| Silent corrupt checkpoint | G | EXP-DR-06 |
| Disable idempotency | G | INV-008 |

Full priority scores: `research/results/capability_priority.json`
