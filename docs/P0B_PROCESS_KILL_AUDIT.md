# P0-B OS Process-Kill Recovery Audit

## Scenarios executed

| Scenario | Mechanism | Outcome |
|----------|-----------|---------|
| SIGKILL at INIT…RUNNING | real child + SIGKILL | unsafe READY=0, unsafe exec=0 |
| before_save | corrupt flag | no unsafe exec |
| partial_write | truncated JSON in SQLite | fail-closed load |
| semantic_invalid READY | in-child save attempt | rejected by P0-A gate |
| restart UNKNOWN | preseeded CP | not executable |
| restart SAFE_MODE | preseeded CP | not executable |
| restart stale RUNNING | raw SQL stale ns | not trusted |
| INV-008 retries | ExecutionStore | 50/50 blocked |

## Safety assessment

No changes to RiskEngine, SAFE_MODE, LIVE gates, fallback, or ExecutionEngine.
Checkpoint still cannot grant execution authority alone.

## Verdict dependency

Local matrix GREEN. GitHub CI must be confirmed separately for full P0-B PASS.
