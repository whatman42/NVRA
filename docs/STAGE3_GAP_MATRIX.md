# Stage 3.1 Gap Matrix — State / Checkpoint / Crash Recovery

| Store | Trust | Status |
|-------|-------|--------|
| institutional CheckpointStore | semantic fail-closed; trusted_execution never from checkpoint | QUALIFIED |
| orchestration CheckpointStore | hash mismatch → CORRUPTED | QUALIFIED |
| ExecutionStore | idempotency | QUALIFIED (component) |
| crypto recovery storage | integrity_check | PASS_COMPONENT |

| Scenario | Expected | Actual |
|----------|----------|--------|
| truncated JSON | reject / not trusted | PASS |
| corrupted bytes | reject | PASS |
| stale | not trusted_ready | PASS |
| schema mismatch | reject or not trusted | PASS |
| READY without recon | reject / not trusted | PASS |
| invalid lifecycle | reject | PASS |
| checkpoint → execution alone | NEVER | PASS (trusted_execution=False) |

| Environment | Status |
|-------------|--------|
| Windows NVRA.exe kill/restart | PASS (Stage 2.5, 5/5, HEAD 22e6b11) |
| Linux systemd service E2E | SERVICE_E2E_UNOBSERVABLE |

**Verdict:** GO-MORE-DATA until full CI GREEN on Stage 3 HEAD + optional deeper ExecutionEngine idempotency E2E.
