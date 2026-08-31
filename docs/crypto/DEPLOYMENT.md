# Deployment

## Editions

| Edition | Program location | User data |
|---------|------------------|-----------|
| **Installer** | `Program Files\CRYPTO` | `%LOCALAPPDATA%\CRYPTO` |
| **Portable** | folder with `CRYPTO.exe` + `.portable` | same folder (`data/`, `state/`, …) |
| **Dev** | repository | repo root or `CRYPTO_HOME` |

`PathResolver` is the **only** path authority. CWD is never used for data location.

## Installer

Built with Inno Setup (`packaging/CRYPTO.iss`) after PyInstaller One-Folder build.

- Optional Desktop / Start-with-Windows shortcuts  
- Stops running `CRYPTO.exe` before upgrade  
- Uninstall **preserves** `%LOCALAPPDATA%\CRYPTO`  
- No Windows Defender exclusions  

## Portable

```powershell
powershell -File scripts/build_portable.ps1
```

Copy the entire `CRYPTO-Portable` folder to another PC. Re-enter API credentials (Credential Manager is machine-local). State/models/audit travel with the folder.

## Start with Windows / Task Scheduler

Shortcuts may start with CWD = `System32`. Application still resolves data via `PathResolver` (install mode → LocalAppData).
