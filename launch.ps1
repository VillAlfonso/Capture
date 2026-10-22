param([ValidateSet('start','stop','restart','monitor')][string]$Action = 'start')
$ErrorActionPreference = 'Stop'
$packagePaths = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package-paths.json') -Raw | ConvertFrom-Json
$appExecutable = Join-Path $PSScriptRoot $packagePaths.app
$monitorExecutable = Join-Path $PSScriptRoot $packagePaths.monitor
if (-not (Test-Path -LiteralPath $appExecutable)) { throw 'Build the application first with build.ps1.' }
if ($Action -eq 'monitor') { & $monitorExecutable; exit $LASTEXITCODE }
if ($Action -in @('stop','restart')) {
    $stopProcess = Start-Process -FilePath $appExecutable -ArgumentList '--stop' -WindowStyle Hidden -Wait -PassThru
    if ($stopProcess.ExitCode -ne 0) { throw 'Stop failed. The application was not restarted.' }
}
if ($Action -in @('start','restart')) {
    Start-Process -FilePath $appExecutable -ArgumentList '--start-paused' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden
}
