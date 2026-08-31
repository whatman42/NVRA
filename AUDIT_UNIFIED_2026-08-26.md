# NVRA Unified Audit — 2026-08-26

## Inputs
- CRYPTO-Windows-Source-0.1.0-HARDENED.zip: 225 files, 187 Python modules.
- NVRAFX_FIXED_RELEASE.zip: 536 files, 439 Python modules.

## Baseline findings
1. CRYPTO already had a strong lightweight architecture: CCXT exchange abstraction, secure credential store, risk engine, ML governor, ensemble, recovery, GUI, Telegram, packaging and tests.
2. NVRAFX already had broader adaptive intelligence: discovery/selection, evidence fusion, adaptive ML, MT5 runtime, paper portfolio, resilience, policy/readiness gates and Windows packaging.
3. The two repositories duplicated some concerns (ML/resource/risk/lifecycle/GUI) but had different domain strengths.
4. The supplied CRYPTO exchange adapters intentionally disable `create_order`, `cancel_order`, and withdrawal. Therefore the merged product must not claim autonomous crypto live execution or withdrawals merely because the GUI has credentials.
5. NVRAFX explicitly blocks live capital by default and requires the existing MT5 readiness/authorization path.
6. IDX functionality is signal-only and is implemented as a separate simulated IDR portfolio.

## Merge design
- `god/` retained as the Forex/N.U.N.G. engine.
- `src/crypto/` retained as the Crypto engine.
- `nvra_unified/` added as the single application control plane.
- One adaptive hardware profile drives resource choices; risk limits remain independent of hardware.
- Broker/account portfolios are represented separately.
- Persistent non-secret configuration is stored under the application data directory.
- Secrets use Windows Credential Manager/keyring where available.
- GUI close hides to tray; runtime supervisor remains alive.
- Graceful stop drains for a configurable period before stopping.

## Requested authentication
The requested username is `nung`. The supplied password is represented by a PBKDF2 verifier, not plaintext source. Registration uses `NVRA_REGISTRATION_SECRET`.

## Telegram
Token/chat ID are stored as secrets. The UI provides status/portfolio controls and a cashout-request path. Because the supplied exchange adapters explicitly disable withdrawal, cashout is fail-closed and cannot falsely report an IDR transfer.

## Tests performed
- Python compileall: PASS.
- Unified smoke: PASS.
- CRYPTO + unified tests: 286 PASS.
- Selected NVRAFX MT5/adaptive-ML suites: 71 PASS.
- Registration-secret CLI path: PASS.
- Full Windows EXE build: NOT RUN here because this environment is Linux and does not contain PyInstaller/PySide6/MetaTrader5 Windows runtime. GitHub Actions is configured as the authoritative Windows build gate.
- Full NVRAFX test suite was not completed in this audit run because the suite is substantially larger/longer; targeted MT5/ML gates passed.

## Hardware targets
- ULTRA_LITE: <=2.5 GB RAM.
- LITE: <=4.5 GB RAM or <=2 logical CPUs.
- BALANCED: <=8 GB RAM.
- PERFORMANCE: <=16 GB RAM.
- EXTREME: >16 GB RAM.
Heavy XGBoost/CatBoost are separated into `requirements-ml-full.txt`.

## Important production limitation
This is an integration/build hardening pass, not a claim that real-money trading has been certified. Actual Windows exchange/MT5 connectivity, permissions, order round-trip, reconciliation, Telegram delivery and any real withdrawal capability still require a live Windows canary under the existing safety gates.

## Release
GitHub workflow: `.github/workflows/unified-windows-build.yml`.
Portable output: `NVRA-Unified-Windows-x64.zip`.
Executable: `NVRA.exe`.
Install helper: `install_to_c.ps1` (default `C:\NVRA`).
