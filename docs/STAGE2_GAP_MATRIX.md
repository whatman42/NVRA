# Stage 2 Gap Matrix

| Surface | Existing coverage | Required | Gap |
|---------|-------------------|----------|-----|
| synthetic replay | PASS | PASS | none |
| RiskEngine | PASS (harness) | PASS | deep evaluate signature still light |
| ExecutionStore/idempotency | PARTIAL (intent hash) | PASS | full store round-trip not in harness |
| EventBus | PARTIAL (publish/consume) | FULL | worker+handlers product drain incomplete |
| orchestration | RESTORED_MINIMAL models | FULL | handler engines optional/no-op |
| startup composition | PARTIAL | FULL | NVRA.exe product path not replay-qualified |
| analysis pipeline | PARTIAL synthetic | FULL | research/ML pipeline not integrated |
| checkpoint/recovery | P0 qualified | FULL replay | recovery-boundary hash matrix incomplete |
| artifact hashing | PASS in scope | FULL | product surface incomplete |
| state hashing | PASS in scope | FULL | product surface incomplete |
| result hashing | PASS in scope | FULL | product surface incomplete |
| failure/recovery replay | PARTIAL (P0-B) | reproducible across boundaries | Stage 2 boundary matrix incomplete |

**Replay scope:** INTEGRATED_PARTIAL  
**Verdict:** GO-MORE-DATA
