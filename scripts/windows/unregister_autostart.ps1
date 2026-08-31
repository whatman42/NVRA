[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$ExecutablePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Keep the same validation contract as registration; the path is not executed.
if ([string]::IsNullOrWhiteSpace($ExecutablePath)) { throw "ExecutablePath is required." }
if (-not [System.IO.Path]::IsPathFullyQualified($ExecutablePath)) { throw "ExecutablePath must be absolute." }
if ($ExecutablePath -match '[\x00-\x1F\r\n"`;&|<>]') { throw "ExecutablePath contains unsupported characters." }
if ([System.IO.Path]::GetExtension($ExecutablePath) -ine ".exe") { throw "ExecutablePath must end in .exe." }

$taskName = "NVRA-AutoStart"
$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($null -ne $task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "Removed $taskName."
} else {
    Write-Host "$taskName is not registered."
}
