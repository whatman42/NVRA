# NVRAFX Final Engineering Audit — 2026-08-26

## Scope
Repository supplied as `fx-main.zip`. Audit covered Python source, tests, MT5 execution gateway, ML promotion lifecycle, packaging, GUI entrypoint, dependency manifest, secret scanning, and Windows build workflow.

## Critical findings found and corrected

1. `god/broker/mt5/adapter.py` was corrupted.
   - The file contained escaped source text and a placeholder instead of executable Python.
   - Result: test collection failed with `SyntaxError`.
   - Corrected with a complete fail-closed MT5 adapter implementing connection, account mode detection, health, ticks, broker constraints, positions/orders, idempotent order submission, reconciliation and audit.

2. `tests/test_mt5_execution.py` contained `PLACEHOLDER`.
   - Replaced with four executable adapter tests covering DEMO connection, order/idempotency, LIVE blocking and constraints.

3. No functional PySide6 GUI existed despite PySide6 being listed as a dependency.
   - Added `god/gui/main.py`.
   - GUI provides dashboard, account registration/login, MT5 connection status, DEMO verification gate, configuration view and audit output.
   - GUI never auto-arms LIVE and does not bypass execution/risk/readiness gates.

4. The Windows runtime did not explicitly install the MetaTrader5 Python package.
   - Enabled `MetaTrader5>=5.0.45; platform_system=="Windows"` in `requirements.txt`.
   - This is required so the Windows PyInstaller build can package the Python MT5 API.

5. ML transactional promotion gate compared challenger OOS accuracy against incumbent training accuracy when the incumbent had no OOS accuracy.
   - Corrected to compare like-for-like OOS evidence only.
   - Existing reliability test now passes.

6. Windows workflows did not explicitly smoke-test GUI import.
   - Added a Windows `GUI_IMPORT_OK` import smoke step before packaging.

## Verification performed

- Python compilation of all `god`, `scripts` and `tools` Python files: PASS.
- Secret scan: PASS.
- `NVRAFX --version`: PASS.
- `NVRAFX --health`: PASS.
- `NVRAFX --check-config`: PASS.
- ML reliability suite: 22 passed.
- MT5 adapter suite: 4 passed.
- ML/DEMO integration suite: 15 passed.
- Product packaging suite: 9 passed.
- Research suite: 12 passed.
- Market decision suite: 14 passed.
- Adaptive ML suites: PASS when run independently.
- Agent, bridge, capital/risk, curiosity, evidence, experiment, healing, installer, IPC, memory, ML hardening/lifecycle, autonomous loop, reliability, auth/persistence, admin/comms, single-exe, voice/Gemini and Windows mock suites: PASS when run independently.
- Windows-specific integration marker remains intentionally skipped on Linux because it requires a real Windows host.

## Important deployment boundary

This environment is Linux and has no Windows PyInstaller runtime, no MetaTrader 5 terminal and no broker account. Therefore a real `NVRAFX.exe` binary cannot be honestly claimed as built or broker-verified from this environment.

The repository is prepared for the Windows build workflow. The workflow builds `NVRAFX.exe`, verifies CLI health/configuration, verifies GUI import, runs regression/security checks, hashes the executable and packages the release.

## LIVE status

LIVE capital remains fail-closed by design.

The codebase contains the LIVE control boundary, but this audit does NOT authorize real-money trading. A real-money certification requires execution on Windows against the intended MT5 terminal/broker, account/server identity verification, market-data freshness verification, order/fill/reconciliation tests, restart/recovery tests and an explicit operator authorization step.

This is intentional. A source-level audit cannot prove broker-side live execution correctness.

## Release artifact

The supplied archive has been repaired and repackaged as a source release containing the corrected code, tests, GUI, packaging spec, workflows and this audit report.

Expected Windows product binary:
`NVRAFX.exe`

Forbidden product binaries:
`NUNG.exe`
`NVRA.exe`
