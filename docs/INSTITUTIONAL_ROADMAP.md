# COMM-01 — Institutional Capability Roadmap

**Non-implementing plan.** Production unchanged in COMM-01.

## PHASES

**I Foundation** — orch models ticket; checkpoint schema design; operator authority docs; freeze invariants as gates.

**II Institutional Research** — experiment runner; brokerage models; walk-forward/OOS; CPCV/PBO libraries.

**III Portfolio/Risk** — constraints, concentration, CVaR research (no live ceiling changes); post-trade analytics.

**IV OMS/EMS/Execution** — cancel/replace depth; multi-venue adapters; external SOR via controlled adapters; never bypass RiskEngine.

**V Distributed Research** — artifact store; workers; ResourceGovernor-aware jobs.

**VI Agentic Research** — advisory only; Evidence→Decision→Governance→Risk unchanged.

**VII Production Institutionalization** — only after INV-001/010 E2E + process recovery evidence; RBAC deepen; SRE/MTTR.

## P0

- Institutional checkpoint schema/version/staleness validation (design→ticket)
- Orchestration models package restoration (engineering ticket)
- Unified experiment registry API (research→product)
- Brokerage/fee/slippage model pack (optional research models)
