$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Security
$secret = Read-Host 'OpenAI API key (leave blank for rehearsal or to keep the existing key)' -AsSecureString
if ($secret.Length -gt 0) {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
    try {
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $bytes = [Text.Encoding]::UTF8.GetBytes($plain)
        $protected = [Security.Cryptography.ProtectedData]::Protect($bytes, $null, [Security.Cryptography.DataProtectionScope]::CurrentUser)
        [IO.File]::WriteAllBytes((Join-Path $PSScriptRoot 'openai-key.dpapi'), $protected)
        [Array]::Clear($bytes, 0, $bytes.Length)
        $plain = $null
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        $secret.Dispose()
    }
}
Write-Host 'OpenAI key setup finished. OPENAI_API_KEY, if set, overrides this saved key. Restart an OpenAI-enabled build before use.'
