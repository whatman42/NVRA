# NVRAFX GUI / Auto-start / Notification Sound Final Audit

Date: 2026-08-28

## Source of truth
- Baseline: `../nvra_pristine`
- Functional modules are preserved except one narrowly scoped governor timing defect fix required by the existing baseline tests.

## Corrective fix
`src/crypto/governor/engine.py`
- The injected `now_fn` is now assigned before `_state_entered_at`.
- Initial governor dwell timing therefore uses the same monotonic clock as subsequent evaluations.
- This fixes all six existing governor assertion failures without changing thresholds, states, risk policy, or execution authority.

## Requested GUI behavior
- Crypto: PAPER / LIVE selector.
- Forex / MT5: no Demo/Real selector; displayed mode follows the connected MT5 account.
- IDX: SIGNAL ONLY / PORTFOLIO integrated; no broker execution control added.
- Windows auto-start: HKCU Run, standard user scope.
- Notification sound: enabled by default, persistent mute toggle, test button.
- NVRA logo and `nvra.ico` retained for GUI / executable packaging.

## Tests
- Governor regression: 11 passed.
- GUI/autostart/notification/MT5/broker focused regression: 22 passed.
- Crypto suite: 282 passed.
- Windows + security + unified + migration: 30 passed, 1 Windows-host-only test skipped on Linux.
- Full monolithic pytest run was not allowed to complete within the 5-minute environment wall-clock limit; no assertion failure was observed after the governor fix before timeout. Slow suites were also run individually and passed.

## Static audit
- No stale GUI strings for `LIVE CAPITAL BLOCKED` or `Run MT5 DEMO Gate` remain.
- `nvra.ico`, `nvra_logo.png`, and notification helper are present.
- Python compilation check passed.
- No `__pycache__`, `.pyc`, or temporary `ml_registry` artifacts are included in release.
- Baseline delta is limited to GUI/assets/autostart/packaging/entry wiring, the new GUI notification helper/tests, and the narrowly scoped governor timing correction.
