# Autonomous Sync Log

## Purpose
Synchronize full autonomous trading lifecycle to `main`.

## Files synchronized
- `god/live/controller.py` (`arm_from_admin_policy`, capital via `allow_live_execution`)
- `scripts/nvrafx_entry.py` (`--autostart --headless`)
- `tests/test_autonomous_trading.py`
- `god/live/autonomous_policy.py`
- `god/live/autonomous_runtime.py`
- `god/mt5_runtime/safety_gate.py`
- `god/live/authorization.py` (`resume_from_admin_policy`)
- `docs/AUTONOMOUS_TRADING.md`, `docs/AUTOSTART.md`
- Windows `register_autostart.ps1` args: `--autostart --headless`

## Local validation
- `compileall`: PASS
- registry: 3 passed
- autonomous tests: 21 passed
- full suite: **806 passed, 1 skipped**

## Remote commits (this sync wave)
- See `main` history for `feat(entry)`, `feat(live): arm_from_admin_policy`, tests, policy, runtime

## Design confirmation
- GUI not required for autonomous runtime
- No login required each reboot after admin setup
- DEMO/PAPER autonomous
- LIVE autonomous after administrative activation
- Fail-closed on precheck failure
- No secrets in policy
- ML/Governor cannot grant administrative authorization
- Strategy/risk/execution math unchanged

## Windows Build
- Triggered after push; fill run ID / artifact SHA when complete
