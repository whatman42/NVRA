# Windows Auto-start

Run PowerShell as the intended non-administrator user.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\register_autostart.ps1 `
  -ExecutablePath "C:\Users\<user>\AppData\Local\NVRA\NVRA.exe"
```

The task is triggered at user logon, runs with **Limited** privileges, and requests up to five restarts at one-minute intervals.

Remove it with:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\windows\unregister_autostart.ps1 `
  -ExecutablePath "C:\Users\<user>\AppData\Local\NVRA\NVRA.exe"
```

`ExecutablePath` must be absolute and end in `.exe`. Do not place secrets in the script or Task Scheduler arguments.
