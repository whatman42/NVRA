# CRYPTO Windows x64 One-Folder release (authoritative).
# Run on Windows x64 with Python 3.10+.
# Does NOT place LIVE orders. Default remains PAPER.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Version = "0.1.0"
$GitSha = (git rev-parse HEAD).Trim()
$Ts = Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
$PyVer = python -c "import sys; print(sys.version.split()[0])"
python -m pip install -U "pip" "wheel" "setuptools"
python -m pip install -e ".[dev,gui,ml-full,windows-secure,packaging]"
# GUI optional — uncomment for GUI release:
# python -m pip install -e ".[gui]"

Write-Host "Running test suite..."
python -m ruff check src tests
python -m ruff format --check src tests
python -m mypy src
python -m pytest -q
if ($LASTEXITCODE -ne 0) { Write-Error "Tests failed"; exit 1 }

Write-Host "Building One-Folder..."
python -m PyInstaller packaging/CRYPTO.spec --noconfirm --clean
$Dist = Join-Path $Root "dist\CRYPTO"
$Exe = Join-Path $Dist "CRYPTO.exe"
if (-not (Test-Path $Exe)) { Write-Error "CRYPTO.exe missing"; exit 1 }

foreach ($d in @("data","models","registry","state","cache","logs","audit","backups")) {
    $p = Join-Path $Dist $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

Write-Host "Smoke..."
& $Exe --version
& $Exe --paths
& $Exe --smoke
if ($LASTEXITCODE -ne 0) { Write-Error "Smoke failed"; exit $LASTEXITCODE }

# Portable copy
$Portable = Join-Path $Root "dist\CRYPTO-Portable"
if (Test-Path $Portable) { Remove-Item -Recurse -Force $Portable }
Copy-Item -Recurse $Dist $Portable
Set-Content -Path (Join-Path $Portable ".portable") -Value "CRYPTO portable edition`n"
& (Join-Path $Portable "CRYPTO.exe") --smoke
if ($LASTEXITCODE -ne 0) { Write-Error "Portable smoke failed"; exit $LASTEXITCODE }

# SHA-256
$Hash = (Get-FileHash -Algorithm SHA256 $Exe).Hash.ToLower()
$Sums = Join-Path $Root "dist\SHA256SUMS.txt"
@"
# CRYPTO Windows x64 release
# version=$Version
# git=$GitSha
# built=$Ts
# python=$PyVer
$Hash  CRYPTO/CRYPTO.exe
"@ | Set-Content -Path $Sums -Encoding utf8

# Release ZIP (One-Folder tree)
$ZipName = "CRYPTO-Windows-x64-$Version.zip"
$ZipPath = Join-Path $Root "dist\$ZipName"
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path $Dist -DestinationPath $ZipPath

# Metadata
$Meta = Join-Path $Root "dist\RELEASE.json"
@"
{
  "version": "$Version",
  "git_sha": "$GitSha",
  "built_at": "$Ts",
  "python": "$PyVer",
  "architecture": "windows-x64",
  "package_type": "one-folder",
  "exe": "CRYPTO/CRYPTO.exe",
  "sha256_exe": "$Hash",
  "zip": "$ZipName",
  "default_mode": "PAPER",
  "production_live": "NOT_YET_VERIFIED"
}
"@ | Set-Content -Path $Meta -Encoding utf8

Write-Host "RELEASE OK"
Write-Host "EXE: $Exe"
Write-Host "SHA256: $Hash"
Write-Host "ZIP: $ZipPath"
Write-Host "PRODUCTION LIVE = NOT YET VERIFIED"
