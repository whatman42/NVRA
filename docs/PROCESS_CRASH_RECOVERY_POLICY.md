# Process Crash Recovery Policy (P0-B)

## Evidence class

**E4 — real OS subprocess + SIGKILL**, not in-process simulation only.

Worker: `research/harness/process_recovery_worker.py`  
Tests: `tests/test_os_process_crash_recovery.py`

## Guarantees under test

1. After SIGKILL + restart recovery:
   - invalid/corrupt checkpoint → not trusted READY
   - UNKNOWN / SAFE_MODE → not executable
   - stale lifecycle → not trusted READY
   - checkpoint never grants execution authority by itself
   - READY without reconciliation cannot be trusted
2. Semantic-invalid READY without recon is rejected by P0-A gate in-child
3. INV-008 idempotency path unchanged and covered

## MTTR

Measured only for **local subprocess recover mode** (load checkpoint + validate + risk probe).

| Metric | Scope |
|--------|--------|
| kill_wait_s | SIGKILL wait |
| kill_to_recover_done_s | recover subprocess wall time |
| Production service MTTR (systemd/Windows service) | **NOT OBSERVABLE** in this gate |

## Non-claims

- Not full NVRAFX.exe GUI kill recovery
- Not multi-host HA
- Not INV-001 / INV-010 LIVE E2E
