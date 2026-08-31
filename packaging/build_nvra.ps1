$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
python -m pip install -r requirements.txt
python -m pip install pyinstaller pytest
python -m pytest tests/ -q --tb=line
python -m PyInstaller packaging\nvrafx_onefile.spec --noconfirm --clean
if (-not (Test-Path dist\NVRAFX.exe)) { throw "NVRAFX.exe missing" }
if (Test-Path dist\NUNG.exe) { throw "NUNG.exe must not be produced" }
if (Test-Path dist\NVRA.exe) { throw "NVRA.exe must not be produced" }
Get-FileHash dist\NVRAFX.exe -Algorithm SHA256
& .\dist\NVRAFX.exe --version
Write-Host "Product binary: NVRAFX.exe only. GUI + NVRA icon + Windows auto-start enabled. LIVE remains disabled."
