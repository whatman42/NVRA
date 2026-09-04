# Stage 2.2 Gap Matrix

| Surface | Runs | Equal | Divergence | Status |
|---------|------|-------|------------|--------|
| EventBus | 100 | yes | yes | PASS |
| Worker | 100 | yes | — | PASS |
| Multi-handler (7 handlers, engines=None) | 100 | yes | order-dependent | PASS_FIXTURE |
| RiskEngine | 100 | yes | yes | PASS |
| ExecutionStore | 100 | yes | — | PASS (2.1) |
| Recovery B1–B6 | — | yes | — | PASS (2.1) |
| Analysis | 20+ | yes | yes | PASS_synthetic_internal |
| Research | 20+ | yes | — | PASS_internal_from_analysis |
| Decision | 20+ | yes | — | PASS_paper |
| run_startup composition | 20 | yes | — | PASS_PAPER |
| NVRA.exe full GUI composition | — | — | — | UNOBSERVABLE |

**Replay scope:** INTEGRATED_PARTIAL  
**Coverage methodology:** product surfaces exercised with DI engines=None + synthetic internal analysis; NVRA.exe GUI composition not replayed beyond CLI/run_startup.  
**Verdict:** GO-MORE-DATA
