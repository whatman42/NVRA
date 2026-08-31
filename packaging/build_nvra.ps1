$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..
python -m pip install -r requirements.txt
python -m pip install pyinstaller pytest
python -m PyInstaller packaging/nvra_onefile.spec --noconfirm --clean
if (-not (Test-Path dist\NVRA.exe)) { throw "NVRA.exe missing" }
if (Test-Path dist\NVRAFX.exe) { throw "NVRAFX.exe must not be produced as product binary" }
if (Test-Path dist\NUNG.exe) { throw "NUNG.exe must not be produced" }
Write-Host "Built dist\NVRA.exe size=$((Get-Item dist\NVRA.exe).Length)"
