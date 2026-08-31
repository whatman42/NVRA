# NVRA Unified Release Manifest

Product: NVRAFX
Release line: Institutional Unified
Execution policy: PAPER ONLY
Broker live orders: DISABLED
Canonical Windows binary: NVRAFX.exe
Python: 3.12–3.13

## Repository contents
- Complete supplied source tree retained.
- Generated Python bytecode/cache excluded.
- Canonical YAML configuration: `config/settings.yaml`.
- Canonical dependency contract: `requirements.txt`.
- Canonical Windows one-file spec: `packaging/nvrafx_onefile.spec`.
- Canonical audit: `AUDIT_DEEP_RELEASE.json` and `AUDIT_DEEP_RELEASE.md`.

## Validation performed locally
- Static AST audit: PASS
- Syntax/compileall: PASS
- Targeted product/ML/MT5/unified tests: 35 passed
- CRYPTO tests: 282 passed
- Windows tests on non-Windows host: 22 passed, 1 expected Windows-only skip
- Full mixed suite: not claimed as complete; long-running root test suite exceeded local execution window.

## Packaging contract
PyInstaller one-file embeds the Python interpreter and installed Python package dependencies into `NVRAFX.exe`. External configuration, persistent state, market data and secrets are intentionally not embedded.
