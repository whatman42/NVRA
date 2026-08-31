# Windows Packaging (Phase 12)

## Target

**One-Folder** Windows x64:

```
dist/CRYPTO/
  CRYPTO.exe
  _internal/
  resources/
  data/ models/ registry/ state/ cache/ logs/ audit/
```

No Python/pip required at runtime. **Installer is Phase 13.**

## Build (Windows)

```powershell
pip install -e ".[dev]"
pip install pyinstaller
# optional GUI:
pip install -e ".[gui]"
powershell -File scripts/build_windows.ps1
```

## Entrypoint safety

- `multiprocessing.freeze_support()` before work
- only `MainProcess` runs full boot
- CLI: `--smoke`, `--paths`, `--version`

## PathResolver

- Frozen: directory of `CRYPTO.exe`
- Dev: repository root (`pyproject.toml`)
- Override: `CRYPTO_HOME`
- SQLite/logs always under user-data dirs — never `_MEIPASS`

## Secrets

CredentialStore / Windows Credential Manager only. Never in `data/`, logs, or package resources.

## Smoke

```bash
python -m crypto --smoke
# or after build:
dist\CRYPTO\CRYPTO.exe --smoke
```

CI must never place real orders. Default mode is **PAPER**.


## Windows release (One-Folder)

On a **Windows x64** machine with Python 3.10+:

```powershell
powershell -File scripts/release_windows.ps1
```

Produces:

- `dist/CRYPTO/CRYPTO.exe` (+ `_internal/`)
- `dist/CRYPTO-Portable/` (with `.portable`)
- `dist/CRYPTO-Windows-x64-<version>.zip`
- `dist/SHA256SUMS.txt`
- `dist/RELEASE.json`

Pre-check on any host:

```bash
bash scripts/verify_release.sh
```

Default mode remains **PAPER**. Production LIVE stays **NOT YET VERIFIED** until operator canary.
