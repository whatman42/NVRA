# NVRA — Phase 1 Fixes

Date: 2026-08-29
Source baseline: `NVRA-UNIFIED-V8-GUI-NVRA-AUTOSTART-SOUND-FINAL.zip`

## Scope

Phase-1 cleanup and compatibility hardening based on the supplied Phase 0/Phase 1 audit artifacts. No trading strategy, risk ceiling, broker authorization rule, portfolio rule, or execution authority was intentionally changed.

| File | Line(s) | Problem type | Fix applied |
|---|---:|---|---|
| `pyproject.toml` | 9 | Python version metadata too restrictive | Changed `requires-python` from `>=3.12,<3.14` to `>=3.10` to match the requested Python 3.10+ compatibility target. |
| `tools/institutional_audit.py` | 6 | Unused import | Removed unused `re` import. |
| `tools/institutional_audit.py` | 9, 16-23 | Audit false-positive on binary assets | Limited UTF-8/NUL/control-character text checks to text-like suffixes so PNG/ICO assets are not treated as UTF-8 source files. |
| `nvra_unified/config.py` | 2, 5 | Unused imports | Removed unused `os`, `tempfile`, and `typing.Any`. |
| `nvra_unified/runtime.py` | 2 | Unused imports | Removed unused `os` and `traceback`. |
| `nvra_unified/auth.py` | 4 | Unused import | Removed unused `typing.Optional`. |
| `nvra_unified/gui.py` | 7, 11-13 | Unused imports | Removed unused `QCheckBox`, `verify_registration_secret`, `verify_totp`, `check_device`, and `AppConfig`. |
| `god/idx/market_rules.py` | 3 | Unused import | Removed unused `Decimal`. |
| `god/institutional/execution_state.py` | 5 | Unused import | Removed unused `ClassVar`. |
| `god/institutional/kernel.py` | 3 | Unused import | Removed unused `field`. |
| `god/observability/models.py` | 5, 7 | Unused imports | Removed unused `field` and `Optional`. |
| `god/observability/diagnostics.py` | 6 | Unused import | Removed unused `Optional`. |
| `god/observability/service.py` | 5 | Unused import | Removed unused `Optional`. |
| `god/observability/metrics.py` | 5-6 | Unused imports | Removed unused `field` and `Any`. |
| `god/app/nung_app.py` | 21 | Unused import | Removed unused `LicenseStore`. |
| `god/orchestration/validation.py` | 7 | Unused import | Removed unused `EventType`. |
| `god/orchestration/worker.py` | 11-17 | Unused imports | Removed unused `CognitiveContext` and `FailureClass`. |
| `god/windows_runtime.py` | 1-92 | Missing module/import compatibility | Added a paper-only compatibility facade required by the existing legacy `god.runtime.main` entrypoint. It delegates to the existing unified runtime and does not add a broker execution path. |
| `god/deployment.py` | 1-43 | Missing module/import compatibility | Added a paper/readiness-only compatibility facade required by `god.release.readiness`. It does not submit broker orders and does not replace the existing bridge installer/healing path. |
| `tests/test_phase1_import_fixes.py` | 1-19 | Regression coverage | Added import/headless-cycle regression tests for the repaired compatibility interfaces. |
| `*.pyc`, `__pycache__/` | entire tree | Generated artifacts | Removed all Python bytecode/cache artifacts before release packaging. |

## Dependency validation

`requirements.txt` already contains the third-party packages imported by the source tree, including PySide6, PyYAML, NumPy, psutil, CCXT, keyring, MetaTrader5 (Windows-only marker), scikit-learn, LightGBM, XGBoost, CatBoost, Torch, SHAP, requests/httpx, Google API dependencies, pytest tooling, PyInstaller, and Prometheus client. No missing third-party package was found by the repository import-to-requirements coverage check.

## Validation

- Python compiler: `python -m compileall -q .` — PASS.
- Python 3.10 syntax parse check — PASS (no files requiring newer syntax).
- Full collected test suite executed in bounded groups: **764 PASS, 1 SKIP**. The skip is the real-Windows-host-only integration marker; Linux cannot execute that test.
- Strict institutional audit — PASS, zero issues.
- Security/secret scan — PASS.
- Deep audit: orphan modules remain non-fatal by design because the repository contains dynamic/optional/compatibility modules; duplicate function groups remain zero.
- `flake8`: not installed in the provided environment. An installation attempt could not reach the package index, so no fabricated flake8 result is reported.

## Business-logic protection

No source file containing trading strategy/risk authority was intentionally changed as part of this phase. The compatibility modules are explicitly paper/readiness-only. Existing Crypto PAPER/LIVE UI behavior, Forex MT5-account detection, IDX signal/portfolio integration, auto-start, NVRA icon, and notification mute functionality are retained from the supplied baseline.
