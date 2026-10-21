$ErrorActionPreference = 'Stop'
$startupLinkPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Quiet Capture.lnk'
$startupShell = New-Object -ComObject WScript.Shell
$startupLink = $startupShell.CreateShortcut($startupLinkPath)
$startupLink.TargetPath = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$startupLink.Arguments = '-B "' + (Join-Path $PSScriptRoot 'app.py') + '"'
$startupLink.WorkingDirectory = $PSScriptRoot
$startupLink.Description = 'Quiet Capture background app; Ctrl+Alt+F9 enables or pauses capture and typing'
$startupLink.Save()
Write-Host 'Quiet Capture will start at Windows sign-in. Ctrl+Alt+F9 toggles capture/typing.'
