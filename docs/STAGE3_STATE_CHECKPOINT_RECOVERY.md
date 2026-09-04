# Stage 3.1 — State, Checkpoint & Crash Recovery

## Production path

`god.institutional.checkpoint.CheckpointStore` validates lifecycle claims on **save** and **load**.

- `trusted_ready` requires valid recon + lifecycle READY/RUNNING
- `trusted_execution` is **always False** from checkpoint alone
- RiskEngine remains mandatory for any execution authorization
- LIVE remains blocked by default

## Labels

| Evidence | Label |
|----------|-------|
| Institutional checkpoint matrix | PRODUCTION_PATH |
| Recovery → RiskEngine chain | PRODUCTION_PATH |
| Windows NVRA.exe process recovery | PRODUCTION_PATH (Stage 2.5) |
| systemd | UNOBSERVABLE |
| Research harness wrappers | RESEARCH_HARNESS |

## Crash boundaries

Windows actual EXE: headless kill/restart PASS (Stage 2.5).
Per-lifecycle GUI composition boundaries remain partially UNOBSERVABLE without interactive desktop.
