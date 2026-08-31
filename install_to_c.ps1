param([string]$Target="C:\NVRA")
$ErrorActionPreference="Stop"
$src = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Test-Path $Target) { Write-Host "Updating $Target" } else { New-Item -ItemType Directory -Path $Target | Out-Null }
Copy-Item -Path (Join-Path $src "*") -Destination $Target -Recurse -Force
Write-Host "NVRA Unified source/portable bundle installed to $Target"
Write-Host "For a built EXE, copy dist\NVRA.exe to $Target and create a shortcut as desired."
