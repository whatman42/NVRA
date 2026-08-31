# Autostart — NVRA

**Product:** NVRA · **Developer:** NUNG

## Windows

```powershell
.\scripts\windows\register_autostart.ps1 -ExecutablePath "C:\NVRA\NVRA.exe"
```

Runs: `NVRA.exe --autostart --headless` at logon (no GUI).

## Oracle / Linux

```bash
sudo systemctl enable nvra
```

ExecStart: `python .../nvrafx_entry.py --autostart --headless`

After administrative setup, reboot resumes autonomous runtime without operator login/ARM if prechecks PASS; otherwise SAFE_MODE.
