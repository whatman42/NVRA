# COMM-01 — Capability Adoption Matrix

## Classes

A ADOPT NOW · B ADOPT AFTER RESEARCH · C ADAPT TO NVRA · D ALREADY COVERED · E NOT WORTH · F EXTERNAL SERVICE ONLY · G REJECT

## Selected mappings

| Capability | NVRA | Adoption |
|------------|------|----------|
| Deterministic experiment evidence | SUPERIOR | D |
| Immutable risk path | SUPERIOR | D |
| Idempotent orders | EXISTS | D |
| Brokerage fee/slippage models | PARTIAL | C |
| Event-driven backtest depth | PARTIAL | C |
| L2/L3 books | MISSING | B |
| CPCV/PBO | MISSING | B |
| Portfolio optimizer | MISSING | B |
| SOR/execution algos | MISSING | F |
| Agent final authority | — | G |
| Silent corrupt recovery | — | G |
| LIVE via fallback | — | G |
| Checkpoint schema gates | PARTIAL | A (ticket; not spontaneous) |
| Orch models package | BLOCKED | A (**separate ticket**) |

## Top 10 NOT to adopt

1. Strategy-side risk override bypassing RiskEngine
2. LLM/agent as final order authority
3. Silent recovery accepting corrupt checkpoints
4. LIVE enable from offline fallback
5. Auto-raise risk ceiling after losses
6. Merged dual RiskEngine without authority design
7. Invented SAFE_MODE on adaptive without design
8. Cloud-only lock-in removing local-first
9. Removing fail-closed defaults for convenience
10. Marketing paper performance as live validation
