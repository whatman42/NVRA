# Checkpoint Schema Policy (Research Target)

## Required fields (research policy v1)

- `schema_version` (str, supported: `1.0`)
- `sequence` (int, non-negative, monotonic)
- `lifecycle` (enum: INIT…RUNNING, SAFE_MODE, FAILED, UNKNOWN)
- `recon_complete` (bool)
- `updated_ns` (int)

## Reject / gate rules

| Condition | Classification |
|-----------|----------------|
| Not an object / bad types | REJECT |
| Missing required fields | RECONCILIATION_REQUIRED |
| Unsupported schema version | REJECT |
| Invalid lifecycle enum | REJECT |
| Sequence regression | REJECT |
| Stale / future timestamp | RECONCILIATION_REQUIRED |
| READY/RUNNING without recon | RECONCILIATION_REQUIRED |
| UNKNOWN | UNKNOWN (no execution) |
| SAFE_MODE | SAFE_MODE (no execution) |
| Exec inconsistency / broker mismatch | RECONCILIATION_REQUIRED |

## Production status

**NOT ENFORCED** on `InstitutionalCheckpointStore` as of this stage.
This document defines the target policy validated by the research harness only.
