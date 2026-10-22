param([string]$ExecutablePath, [switch]$CheckOnly)
$ErrorActionPreference = 'Stop'

# Resolve from this script's location, not the current terminal directory.
if ($ExecutablePath) {
    $selectedPath = if ([IO.Path]::IsPathRooted($ExecutablePath)) { $ExecutablePath } else { Join-Path $PSScriptRoot $ExecutablePath }
    if ([IO.Path]::GetExtension($selectedPath) -ne '.exe' -or -not (Test-Path -LiteralPath $selectedPath -PathType Leaf)) {
        throw 'The specified executable does not exist or is not an .exe file. No shortcuts were changed.'
    }
    $candidatePaths = @($selectedPath)
} else {
    $candidatePaths = @(
        (Join-Path $PSScriptRoot 'QuietCapture.exe'),
        (Join-Path $PSScriptRoot 'dist\QuietCapture\QuietCapture.exe')
    )
}
$existingPaths = @($candidatePaths | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf })
if ($existingPaths.Count -gt 1) {
    throw 'Two QuietCapture.exe builds were found. Keep only the intended build in the supported locations. No shortcuts were changed.'
}
if ($existingPaths.Count -eq 1) {
    $appExecutable = (Resolve-Path -LiteralPath $existingPaths[0]).Path
    $appArguments = '--start-paused'
    $executableFolder = Split-Path -Parent $appExecutable
    $configFolders = @($executableFolder)
    $parentFolder = Split-Path -Parent $executableFolder
    if ($parentFolder) {
        $configFolders += $parentFolder
        $grandparentFolder = Split-Path -Parent $parentFolder
        if ($grandparentFolder) { $configFolders += $grandparentFolder }
    }
} else {
    $appExecutable = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
    $sourcePath = Join-Path $PSScriptRoot 'app.py'
    $pythonConsole = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $appExecutable -PathType Leaf) -or
        -not (Test-Path -LiteralPath $sourcePath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $pythonConsole -PathType Leaf)) {
        throw 'No QuietCapture executable or working Python source installation was found. No shortcuts were changed.'
    }
    & $pythonConsole -B -c 'import PIL, ctypes, ssl'
    if ($LASTEXITCODE -ne 0) { throw 'Python environment failed its dependency check. Run setup.ps1 on this computer.' }
    $appArguments = '-B "' + $sourcePath + '" --start-paused'
    $configFolders = @($PSScriptRoot)
    Write-Host 'Using the existing Python source installation; no build is required.'
}
$configFolder = $configFolders | Where-Object {
    Test-Path -LiteralPath (Join-Path $_ 'config.json') -PathType Leaf
} | Select-Object -First 1
if (-not $configFolder) {
    throw 'config.json is missing from the locations this build reads. Keep the current configuration with the app. No shortcuts were changed.'
}
$config = Get-Content -LiteralPath (Join-Path $configFolder 'config.json') -Raw | ConvertFrom-Json
if (-not $config.model -or -not $config.language -or -not $config.allowed_processes) {
    throw 'config.json lacks model, language, or allowed_processes. No shortcuts were changed.'
}
Write-Host "Executable: $appExecutable"
Write-Host "Configuration folder: $configFolder"
if ($CheckOnly) {
    Write-Host 'Paths and configuration checked. No shortcuts were changed and no app was started.'
    return
}
$shortcutShell = New-Object -ComObject WScript.Shell
foreach ($definition in @(
    @{ Folder = [Environment]::GetFolderPath('Startup'); Name = 'Quiet Capture.lnk'; Hotkey = '' },
    @{ Folder = [Environment]::GetFolderPath('Programs'); Name = 'Quiet Capture Demo.lnk'; Hotkey = 'CTRL+ALT+F8' }
)) {
    $shortcut = $shortcutShell.CreateShortcut((Join-Path $definition.Folder $definition.Name))
    $shortcut.TargetPath = $appExecutable
    $shortcut.Arguments = $appArguments
    $shortcut.WorkingDirectory = $configFolder
    $shortcut.IconLocation = "$appExecutable,0"
    $shortcut.Description = 'Quiet Capture; Ctrl+Alt+F9 toggles capture, Ctrl+Alt+F12 restarts'
    $shortcut.Hotkey = $definition.Hotkey
    $shortcut.Save()
}
Write-Host 'Quiet Capture will start paused at Windows sign-in for this user. Ctrl+Alt+F9 enables it.'
Write-Host 'No app was started. Run this script again after relocating the app.'
