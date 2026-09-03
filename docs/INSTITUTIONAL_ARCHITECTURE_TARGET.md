# COMM-01 — Institutional Architecture Target

```
Research / Agents (advisory)
  → Evidence → Decision → Governance / Policy / License
  → Immutable Risk Governor / RiskEngine
  → Pre-trade validation (DQ, recon, SAFE_MODE, limits)
  → OMS / EMS (NVRA path or external)
  → Execution (path-scoped sole sinks)
  → Reconciliation → Persistent State
```

## Hard rules

1. AI/ML/agents never direct execution authority.
2. LIVE requires explicit authorization (INV-001 still E2E gap).
3. Offline fallback cannot enable LIVE (INV-010).
4. Corrupt/unknown state cannot become trusted READY without recon.
5. Crypto vs MT5 demo remain path-scoped, not dual owners on one sink.

## Prefer

| Layer | Approach |
|-------|----------|
| Research backtest depth | ADAPT LEAN/Nautilus patterns |
| SOR/desk OMS | EXTERNAL SERVICE |
| Risk authority | KEEP NVRA |
| Scientific evidence | KEEP/EXPAND NVRA |
