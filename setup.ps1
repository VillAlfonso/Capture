$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }

Add-Type -AssemblyName System.Security
$secret = Read-Host 'Gemini API key (leave blank for rehearsal or to keep the existing key)' -AsSecureString
if ($secret.Length -gt 0) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $bytes = [Text.Encoding]::UTF8.GetBytes($plain)
        $protected = [Security.Cryptography.ProtectedData]::Protect($bytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        [IO.File]::WriteAllBytes((Join-Path $PSScriptRoot 'key.dpapi'), $protected)
        [Array]::Clear($bytes, 0, $bytes.Length)
        $plain = $null
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $secret.Dispose()
    }
}
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Programs')) 'Quiet Capture Demo.lnk'
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut($shortcutPath)
$shortcut.TargetPath = Join-Path $PSScriptRoot '.venv\Scripts\pythonw.exe'
$shortcut.Arguments = '-B "' + (Join-Path $PSScriptRoot 'app.py') + '"'
$shortcut.WorkingDirectory = $PSScriptRoot
$shortcut.Hotkey = 'CTRL+ALT+F8'
$shortcut.Description = 'Windowless capture and code rehearsal utility'
$shortcut.Save()
& (Join-Path $PSScriptRoot 'enable-startup.ps1')
Write-Host 'Setup complete. Starts at sign-in paused. Ctrl+Alt+F9 enables/pauses; Ctrl+Alt+F12 pauses/cancels. Use stop.cmd to exit.'
Write-Host 'No app has been started. Set rehearsal=true in config.json to test without an API call.'
