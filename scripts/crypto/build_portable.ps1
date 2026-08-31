# Assemble CRYPTO Portable edition from One-Folder build.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Src = Join-Path $Root "dist\CRYPTO"
$Out = Join-Path $Root "dist\CRYPTO-Portable"
if (-not (Test-Path (Join-Path $Src "CRYPTO.exe"))) {
    Write-Error "Run PyInstaller build first (dist\CRYPTO\CRYPTO.exe missing)"
    exit 1
}
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }
Copy-Item -Recurse $Src $Out
# Portable marker — PathResolver uses this
Set-Content -Path (Join-Path $Out ".portable") -Value "CRYPTO portable edition`n"
foreach ($d in @("data","models","registry","state","cache","logs","audit","backups")) {
    $p = Join-Path $Out $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}
Write-Host "Portable package: $Out"
& (Join-Path $Out "CRYPTO.exe") --smoke
if ($LASTEXITCODE -ne 0) { Write-Error "Portable smoke failed"; exit $LASTEXITCODE }
Write-Host "Portable smoke OK"
