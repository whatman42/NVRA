# Stage 3.2 — Final State, Checkpoint & Crash Recovery

## Qualified production path

`god.institutional.checkpoint.CheckpointStore`:

- save/load semantic validation
- `trusted_ready` only with valid recon + lifecycle
- `trusted_execution` **never** granted by checkpoint alone
- RiskEngine remains mandatory for execution authorization

## Windows product recovery (exact HEAD)

HEAD `cb34ac5eb1a8623f65184e68bf7182c7561648b8`  
Run [33850370520](https://github.com/whatman42/nvra/actions/runs/33850370520):

- Build NVRA.exe PASS
- CLI smoke PASS
- `--headless` composition PASS
- process kill/restart recovery PASS
- Artifact NVRA-Windows `9928684607`

## Non-blocking deferrals

| Gap | Stage |
|-----|-------|
| GUI interactive E2E | 9 |
| systemd service E2E | 9 |
| Broker exactly-once | 7/9 |
| MTTR SLA | 9 |

## Production semantics

Unchanged vs Stage 2 baseline for Risk/LIVE/SAFE_MODE/Execution authority.
