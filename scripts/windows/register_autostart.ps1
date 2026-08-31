[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Require a canonical absolute path to an existing .exe.
try {
    $resolved = (Resolve-Path -LiteralPath $ExecutablePath -ErrorAction Stop).Path
} catch {
    throw "ExecutablePath does not exist or cannot be resolved."
}
if (-not [System.IO.Path]::IsPathFullyQualified($resolved)) { throw "ExecutablePath must be absolute." }
if ([System.IO.Path]::GetExtension($resolved) -ine ".exe") { throw "ExecutablePath must point to an .exe file." }
if (-not [System.IO.File]::Exists($resolved)) { throw "ExecutablePath must be a file." }

# Reject control characters and shell/metacharacters in the supplied path.
if ($ExecutablePath -match '[\x00-\x1F\r\n"`;&|<>]') {
    throw "ExecutablePath contains unsupported characters."
}

$taskName = "NVRA-AutoStart"
$action = New-ScheduledTaskAction -Execute $resolved -Argument "--autostart --headless"
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

# Register for the current user only, with limited privileges.
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -RunLevel Limited `
    -Force `
    -Description "NVRA headless autonomous auto-start (non-administrator)."

Write-Host "Registered $taskName for: $resolved"
