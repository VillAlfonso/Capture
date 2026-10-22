param(
    [ValidatePattern('^[A-Za-z][A-Za-z0-9_-]{0,48}$')][string]$AppName = 'QuietCapture',
    [ValidatePattern('^[A-Za-z][A-Za-z0-9_-]{0,48}$')][string]$MonitorName = 'QuietCaptureMonitor'
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($AppName -eq $MonitorName) { throw 'Choose different names for the app and monitor.' }
$env:QUIET_CAPTURE_APP_NAME = $AppName
$env:QUIET_CAPTURE_MONITOR_NAME = $MonitorName
& '.\.venv\Scripts\python.exe' -B build_package.py
if ($LASTEXITCODE -ne 0) { throw 'Build failed; startup was not changed.' }
& (Join-Path $PSScriptRoot 'enable-startup.ps1') -ExecutablePath (Join-Path $PSScriptRoot ('dist\' + $AppName + '\' + $AppName + '.exe'))
