# COMM-01 — Institutional Architecture Target

## Target flow (normative)

```
Research / Agents (advisory)
        ↓
    Evidence
        ↓
    Decision
        ↓
    Governance (license, RBAC, policy)
        ↓
    Immutable Risk Governor / RiskEngine
        ↓
    Pre-trade validation (data quality, recon, SAFE_MODE)
        ↓
    OMS / EMS (lifecycle, idempotency)
        ↓
    Execution (PAPER default; LIVE explicit + auth)
        ↓
    Reconciliation
        ↓
    Persistent State (integrity-gated checkpoints)
```

## Hard rules

1. **AI/ML/agents are never direct execution authority.**
2. **RiskEngine/ExecutionEngine contract remains:** no approved decision → no submit.
3. **SAFE_MODE and reconciliation are veto-capable.**
4. **Fallback/offline cannot grant LIVE** (INV-010).
5. **Idempotent effects** for client order intents (INV-008).
6. **Dual product paths** (crypto vs MT5 demo) stay path-scoped; no silent merge.

## Mapping to NVRA today

| Layer | NVRA today | Gap |
|-------|------------|-----|
| Research/Agents | god/ml, research validation, agents advisory | depth vs Nautilus/LEAN |
| Evidence | EXP-DR packages, hashes | product UX |
| Decision | market_decision, ML pipeline | — |
| Governance | control_plane, LiveAuthorizationGate | tenant prod |
| Risk | RiskEngine + adaptive (path-scoped) | unified policy docs |
| Pre-trade | DQ/recon/SAFE_MODE | — |
| OMS/EMS | ExecutionEngine + store | algos/SOR/UX |
| Execution | PAPER/LIVE mode + adapters | venue scale |
| Reconciliation | portfolio reconcile + gates | depth |
| State | institutional/cycle/exec stores | schema gates; orch BLOCKED |

## Adoption principle

Prefer **ADAPT TO NVRA** over cloning commercial defaults that optimize for convenience over fail-closed governance.
