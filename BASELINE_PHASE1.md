# NVRA Phase 1 Baseline

This release is the post-Phase-1 cleanup baseline for subsequent work.

## Baseline rules

- Preserve existing business logic and execution/risk authority unless a defect is explicitly authorized for correction.
- Do not delete functional Python source files.
- Crypto GUI supports PAPER/LIVE; existing production gates remain authoritative.
- Forex/MT5 follows the account currently connected to the MT5 terminal; NVRA does not provide a Demo/Real selector.
- IDX remains signal-only and integrated with the portfolio.
- Windows auto-start and NVRA GUI/icon/notification-sound behavior are retained.
- No generated Python bytecode/cache artifacts are distributed.

## Validation baseline

- `python -m compileall -q .`: PASS
- Test suite: 764 PASS, 1 SKIP (real-Windows-host-only)
- Strict audit: PASS
- Deep audit: PASS
- Security scan: PASS
- Third-party import coverage vs `requirements.txt`: PASS
- `flake8`: unavailable in the build environment; no fabricated result is claimed.
