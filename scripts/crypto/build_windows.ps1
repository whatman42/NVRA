# Build CRYPTO One-Folder EXE on Windows x64.
# Prerequisites: Python 3.10+, pip install -e ".[dev]" and pyinstaller
# Optional: pip install -e ".[gui]" for PySide6

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install -U ".[gui,ml-full,windows-secure,packaging]"
python -m PyInstaller packaging/CRYPTO.spec --noconfirm --clean

$Dist = Join-Path $Root "dist\CRYPTO"
if (-not (Test-Path (Join-Path $Dist "CRYPTO.exe"))) {
    Write-Error "CRYPTO.exe not found in $Dist"
    exit 1
}

# Portable layout folders (user data — empty at ship time)
foreach ($d in @("data","models","registry","state","cache","logs","audit")) {
    $p = Join-Path $Dist $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

Write-Host "Build OK: $Dist\CRYPTO.exe"
& "$Dist\CRYPTO.exe" --smoke
if ($LASTEXITCODE -ne 0) {
    Write-Error "Smoke test failed"
    exit $LASTEXITCODE
}
Write-Host "Smoke OK"
