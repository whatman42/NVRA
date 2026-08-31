# NVRA Unified — Institutional Paper Trading Platform

NVRA Unified is a modular quantitative research, signal, risk and **paper-trading** platform for Windows. The release package is designed for autonomous operation while remaining fail-closed.

## Non-negotiable execution boundary

- **PAPER ONLY.** This product distribution does not authorize broker/live orders.
- Risk ceilings are immutable at runtime.
- Data, storage, resource or integrity failures enter `SAFE_MODE`.
- Credentials are external: environment variables or Windows Credential Manager/keyring.
- MT5/CCXT code retained in the source tree is compatibility/research infrastructure; the distributed NVRAFX product must not submit live orders.

## Architecture

`data → quality → features → ML governor → regime → ensemble → signal governor → risk governor → paper execution → portfolio → audit/telemetry → Telegram`

Supporting domains include model registry/lifecycle, leakage-aware CPCV with embargo, walk-forward validation, triple-barrier labels, PBO/Deflated Sharpe research, drift/OOD detection, recovery, reconciliation, observability, chaos tests and Windows packaging. CPCV/PBO/DSR are offline governance diagnostics and are never required on the daily execution path.

## Configuration

Canonical configuration is `config/settings.yaml`. No secret belongs in YAML.

Portfolio capital can be reset with:

```yaml
portfolio:
  initial_capital_idr: 10000000
  reset_capital_idr: 10000000
```

Adaptive signal relaxation is bounded:

```yaml
signals:
  adaptive_enabled: true
  buy_threshold: 0.60
  sell_threshold: 0.40
  relaxation_step: 0.02
  max_relaxation: 0.08
```

The signal governor may relax signal thresholds when the market is inactive, but it **cannot relax risk ceilings**.

## ML governance

The complete lightweight/optional model stack is available through the requirements file. Model selection is controlled by the governor; heavy quantitative validation (CPCV/PBO/DSR) belongs to offline model governance, not the daily inference path.

## V8 institutional orchestration

V8 incorporates hardware-bounded architecture patterns inspired by NautilusTrader and
structured multi-agent research patterns inspired by TradingAgents without importing
either project as a runtime dependency.

- `god/institutional/contracts.py`: typed Data/Event/Command/Decision contracts.
- `god/institutional/message_bus.py`: bounded deterministic pub/sub bus with backpressure.
- `god/institutional/execution_state.py`: idempotent order lifecycle and explicit UNKNOWN reconciliation.
- `god/institutional/checkpoint.py`: dependency-light SQLite node checkpoints.
- `god/institutional/agent_graph.py`: typed analyst/evidence/debate decision graph; advisory only.
- `god/institutional/kernel.py`: composition root and checkpoint/audit spine.
- `god/institutional/resource_profiles.py`: 8GB/16GB/32GB/64GB workload profiles.

The existing autonomous control loop publishes typed decisions to this institutional
kernel for checkpointing and audit; the kernel's observation executor is deliberately
non-executing so there is no second order path.

### Hardware policy

8GB DDR3 is the minimum supported host. On 8GB, lightweight ML inference and
sequential training remain enabled while resident neural training is disabled.
At 16GB, the full tree-model stack remains available and neural inference can be
used when Torch is installed; heavy training remains deferred. At 32GB+ heavy
training becomes eligible subject to ResourceGovernor pressure. 64GB+GPU receives
the highest workload profile. Inference always outranks training.

## Deep audit

Run:

```powershell
python tools/deep_audit.py
```

The audit reports:
- syntax errors;
- duplicate definitions;
- external dependency mismatches;
- orphan/unreachable modules from declared product entrypoints;
- conflicting Windows build workflows;
- generated artifacts such as `.pyc`/cache files;
- live-execution surfaces requiring containment;
- packaging and documentation consistency.

## Tests

```powershell
$env:PYTHONPATH = ".;src"
python -m pytest tests/ -q
```

## Windows one-file build

The canonical product is **`NVRAFX.exe`**. PyInstaller `onefile` embeds the Python runtime and installed Python dependencies into the executable. Configuration, persistent state, market data and credentials remain external by design.

GitHub Actions workflow: `.github/workflows/windows-build.yml`.

Release checks include tests, secret scan, compile/import checks, executable smoke tests, SHA-256 and a release manifest.

## Repository hygiene

Do not commit:
- `.pyc`, `__pycache__`, `.pytest_cache`;
- model/data/state runtime artifacts;
- credentials, tokens or private keys.

## Broker modes: DEMO and REAL

Each supported broker has an independent execution mode: `DEMO` or `REAL`.
The canonical profiles are in `config/broker_modes.yaml` and mirrored in
`config/settings.yaml`.

Supported broker profiles:
- Binance
- Tokocrypto
- INDODAX
- MetaTrader 5

`DEMO` uses the broker's native sandbox/testnet when the broker exposes one.
If a broker does not expose a native sandbox, the application must use its
paper simulator rather than silently routing DEMO traffic to production.

`REAL` is intentionally fail-closed. It requires all of the following:
1. broker profile `allow_real: true`;
2. broker mode set to `REAL`;
3. `NVRA_REAL_TRADING_ENABLE=true`; and
4. `NVRA_REAL_TRADING_CONFIRM=I_UNDERSTAND_REAL_TRADING`.

API keys/passwords are never stored in YAML. Use environment variables or
Windows Credential Manager/keyring. For exchanges, the execution adapter only
enables order submission after the real-mode gate passes. For MT5, the adapter
also verifies that the connected account is actually LIVE before accepting a
REAL session.

**Important:** REAL mode is an actual broker/exchange execution capability.
Use a dedicated account, minimum permissions, and independent risk controls.
Never test REAL mode with credentials for an account containing capital you
cannot afford to lose. Withdrawal permission should remain disabled.

## V7 IDX & operational hardening

V7 adds configurable IDX order-rule validation (lot/tick/session/ARA-ARB), transaction-cost accounting, corporate-action adjustment events, anti-overtrading controls, durable order journaling/idempotency, fail-closed reconciliation, structured notification severity, extreme-market scenario tests, and a DEMO certification runbook. Regulatory/tax rates are configuration-driven and must be sourced and reviewed by the operator; no legal or tax rate is assumed by the engine.

### Recovery invariant
A timeout or network failure produces `UNKNOWN`, never `FAILED`. On restart, NVRA reconciles local journal, broker orders/fills, positions and balance before permitting new orders. Any unexplained mismatch enters `SAFE_MODE`.

## PC migration / learned-state portability

NVRA provides a checksummed portable migration package so an installation can move to another PC without losing learned model artifacts or runtime/portfolio state. Use `tools/migrate_state.py export` on the old PC and `import` on the new PC. The bundle is allow-listed and excludes credentials/private keys. Every payload file is SHA-256 verified before restore. See `docs/MIGRATION.md`.

Migration is not a blind file copy: after import, NVRA must enter recovery/reconciliation and verify local journal, broker/demo state, positions, orders, fills and balance before permitting new execution intents. If reconciliation is unknown or inconsistent, remain in `SAFE_MODE`.

## V7.1–V8.0 hardening baseline

`NVRA-UNIFIED-INSTITUTIONAL-V7-FINAL-HARDENED.zip` is the source of truth for subsequent releases. Each change is required to pass `python tools/institutional_audit.py` and the regression suite. The roadmap is documented in `docs/PLAN_V7_1_TO_8_0.md`.

### Identity and cloud recovery

NVRA uses Google OAuth 2.0 rather than collecting a Google password. Optional app-level TOTP is compatible with Google Authenticator. Google Drive backup uses least-privilege `drive.file` OAuth and encrypted migration bundles. One-active-device enforcement requires a configured HTTPS license service; if it is not configured, the client explicitly reports `LOCAL_ONLY` and never pretends remote enforcement exists.

## Startup Composition Root

The runtime startup sequence is orchestrated by `src/crypto/runtime/startup.py` and documented in `STARTUP_COMPOSITION_ROOT.md`.

## Production installation and operations

See `docs/INSTALL.md`, `docs/AUTOSTART.md`, `docs/RECOVERY.md`, and `docs/CONFIGURATION.md`.

NVRA has **no default credentials**. First-run enrollment creates the operator credential; passwords/tokens must never be placed in command-line arguments or committed to source control.

Normal/headless entry points:

```powershell
python -m crypto
python -m crypto --no-gui
python -m crypto --smoke
```

For a Windows packaged deployment, use `scripts/windows/register_autostart.ps1` with the absolute path to `NVRA.exe`. The task runs at user logon with Limited privileges and a maximum of five one-minute restart attempts.

Troubleshooting:
- `SAFE_MODE`: inspect runtime logs and resolve the failed prerequisite; startup will remain fail-closed.
- Import errors: recreate the Python environment and reinstall `requirements.txt`.
- Auto-start issues: verify the executable path, Task Scheduler entry `NVRA-AutoStart`, and that the task belongs to the intended user.
- Missing GUI on Linux/headless systems: use `--no-gui`; the core runtime does not require a display.
