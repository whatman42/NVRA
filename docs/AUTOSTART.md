# Windows Auto-start

Production command (headless autonomous core):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\register_autostart.ps1 `
  -ExecutablePath "C:\NVRA\NVRAFX.exe"
```

The task runs:

```text
NVRAFX.exe --autostart --headless
```

- Trigger: user logon
- RunLevel: Limited
- Restart: up to 5 times, 1 minute interval
- **No secrets** in task arguments
- **No GUI** required for trading core

HKCU Run (GUI checkbox) uses the same `--autostart --headless` arguments.

Remove:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\unregister_autostart.ps1 `
  -ExecutablePath "C:\NVRA\NVRAFX.exe"
```

See also: `docs/AUTONOMOUS_TRADING.md`
