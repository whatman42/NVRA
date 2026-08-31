# CRYPTO Architecture

**Phase 0 document — living reference.**

## 1. Product Goal

Deliver a Windows desktop application (`CRYPTO.exe` + `CRYPTO-Setup.exe`) that:

- Connects to multiple crypto exchanges after the user supplies API credentials.
- Runs fully autonomous trading with adaptive ML and strict risk controls.
- Works on hardware ranging from old i3 / <4 GB RAM / HDD up to modern workstations.
- Requires zero technical knowledge from the end user after first-run setup.

## 2. High-Level Component Map

```
CRYPTO.exe
│
├── core/                 # Types, config schema, event foundations, lifecycle
├── hardware/             # Detection + Dynamic Resource Governor
├── exchanges/            # ExchangeAdapter + concrete adapters (CCXT-based)
├── market/               # Data feeds, validation, feature pipeline
├── ml/                   # Classical models, ensemble, registry (inference only)
│   ├── classical/
│   └── plugins/          # Optional deep-learning extensions (EXTREME only)
├── risk/                 # Highest authority — sizing, limits, kill-switch
├── execution/            # Order state machine + reconciliation
├── portfolio/            # Positions, balances, PnL
├── storage/              # SQLite / DuckDB / Parquet (lightweight)
├── recovery/             # Supervisor / watchdog / state restore
├── monitoring/           # Structured logging + audit trail
├── backtesting/          # Walk-forward, fees, slippage
├── gui/                  # PySide6 first-run + status dashboard
└── packaging/            # PyInstaller one-folder (default)
```

## 3. Critical Invariants

### 3.1 Risk Invariant
Hardware profile **MUST NOT** change:
- maximum risk / exposure
- maximum drawdown
- daily loss limit
- kill-switch behaviour
- any safety rule

Hardware profile may only change compute parameters (model count, tree count, feature complexity, inference frequency, worker count, cache size, parallelism).

### 3.2 ML Never Sends Orders
```
ML Signal → Confidence → Risk Engine → ALLOW / REDUCE / REJECT → Execution
```

### 3.3 Training vs Live Inference
Live process performs **inference only**. Training occurs offline on stronger machines; models are promoted through a registry with canary and automatic rollback.

### 3.4 Credentials
API keys/secrets are stored exclusively via OS secure storage (Windows Credential Manager / DPAPI). Never logged, never written to plain files in the application directory.

## 4. Adaptive Runtime Model

The distribution is described as:

> **One application distribution with adaptive runtime**

Not “one monolithic executable containing every possible dependency”.

- Core binary is light.
- Optional ML backends and deep-learning plugins are activated according to the detected HardwareProfile and available packages.
- Default packaging target is **one-folder** layout for reliability on old hardware and better antivirus compatibility. One-file is an optional later release artifact.

## 5. Event-Driven Core (future)

Lightweight internal event bus. Example events (Phase ≥ 1):

- MarketTick, CandleClosed, OrderBookUpdated
- SignalGenerated, RiskApproved
- OrderSubmitted, OrderFilled, PositionChanged
- ModelChanged, HealthChanged, ResourceProfileChanged

## 6. Data Directory (Windows)

```
%LOCALAPPDATA%\CRYPTO\
    config\
    database\
    logs\
    models\
    cache\
    backups\
```

Executable directory is kept clean of user data and secrets.

## 7. Exchange Abstraction

```
ExchangeAdapter (interface)
├── BinanceAdapter
├── TokocryptoAdapter
├── IndodaxAdapter
└── FutureExchangeAdapter
```

Trading engine depends only on the interface. Capability differences are isolated inside each adapter.

## 8. Phase Roadmap Summary

| Phase | Focus                              |
|-------|------------------------------------|
| 0     | Foundation, docs, CI (this doc)    |
| 1     | Core + config + secure credentials |
| 2     | Exchange gateway                   |
| 3     | Market data                        |
| 4     | Portfolio + Risk Engine            |
| 5     | Execution + reconciliation         |
| 6     | Lightweight classical ML           |
| 7     | Ensemble + Model Registry          |
| 8     | Hardware auto-profile              |
| 9     | Dynamic Resource Governor          |
| 10    | Self-recovery                      |
| 11    | GUI (PySide6)                      |
| 12    | Windows EXE (one-folder)           |
| 13    | Installer + Release                |
| 14    | Full integration / paper trading   |
| 15    | Production hardening               |

Each phase follows: **IMPLEMENT → TEST → VERIFY → COMMIT → REPORT**.

## 9. Dependency Philosophy

- Core installation stays minimal.
- Heavy libraries enter only in the phase that requires them.
- ML backends are optional extras.
- Deep learning lives under `ml/plugins/deep_learning/` and is never a core dependency.

## 10. Safety Modes (future)

- Emergency Stop
- Kill Switch
- No-New-Orders Mode
- Read-Only Mode
- Paper Trading Mode

Stale market data, unhealthy exchange connection, or unknown order state → **NO NEW ENTRY**.
