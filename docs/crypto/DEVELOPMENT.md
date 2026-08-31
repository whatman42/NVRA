# Development Guide

## Prerequisites

- Python 3.10+
- Git
- (Windows) Visual C++ Build Tools only if native extensions are later introduced; not required for Phase 0.

## Setup

```bash
git clone https://github.com/whatman42/CRYPTO.git
cd CRYPTO
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -e ".[dev]"
```

## Running Checks (Phase 0)

```bash
# Unit tests
pytest

# Lint
ruff check src tests

# Format check (optional)
ruff format --check src tests

# Type checking
mypy src
```

All of the above must pass before a phase is considered GREEN.

## Project Conventions

- Package lives under `src/crypto/`.
- Tests live under `tests/` and mirror the package structure when useful.
- No heavy dependencies in core.
- Forward-only commits. Never force-push or rewrite shared history.
- Secrets never appear in source, logs, or commit messages.

## Adding a New Phase

1. Implement only what the phase description requires.
2. Add focused tests.
3. Run the full check suite.
4. Commit with a clear message: `phase N: short description`.
5. Update status tables in README and ARCHITECTURE if needed.
6. Report results (files, tests, SHA, limitations).

## Optional Dependency Groups (future)

These groups are declared early for architectural clarity but are **not** installed in Phase 0:

```toml
# ml-lite      → lightgbm
# ml-balanced  → lightgbm + xgboost + scikit-learn + catboost
# gui          → PySide6
# exchange     → ccxt
# storage-duckdb → duckdb
# packaging    → pyinstaller
```

## Windows Packaging Notes (Phase 12+)

Default target: **one-folder** layout.

```
CRYPTO/
    CRYPTO.exe
    runtime/          # or _internal/
    models/
    ...
```

One-file `.exe` is optional and only after one-folder is proven stable.

## Credential Handling Rules

- Never hard-code keys.
- Never commit keys.
- Never log secrets.
- Use OS secure storage (Windows Credential Manager / DPAPI).
- Provide explicit disconnect / delete credential functionality.
