# Windows Deployment — NVRA

**Product:** NVRA · **Developer:** NUNG · **Binary:** `NVRA.exe`

## Artifact

1. Download `nvra-windows-release` from successful **Windows Build**.  
2. Verify SHA-256 via `SHA256SUMS.txt`.  
3. Place at e.g. `C:\NVRA\NVRA.exe`.

## CLI

```powershell
.\NVRA.exe --version
.\NVRA.exe --health
.\NVRA.exe --check-config
.\NVRA.exe --autostart --headless
```

Exit code **0** when healthy.

## Auto-start

```powershell
.\scripts\windows\register_autostart.ps1 -ExecutablePath "C:\NVRA\NVRA.exe"
```

Task: `NVRA-AutoStart` · args: `--autostart --headless` · Limited · restart ≤5× / 1 min.

## Safety

LIVE blocked by default. Policy has no secrets. NUNG is not a credential.
