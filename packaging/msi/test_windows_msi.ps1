param(
    [Parameter(Mandatory = $true)][string]$MsiPath,
    [Parameter(Mandatory = $true)][string]$MetadataPath
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "MSI lifecycle test requires an elevated/administrator runner"
}

$MsiPath = (Resolve-Path -LiteralPath $MsiPath).Path
$MetadataPath = (Resolve-Path -LiteralPath $MetadataPath).Path
$metadata = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
if (-not $metadata.testOnly -or $MsiPath -notmatch 'unsigned-test-only\.msi$') {
    throw "Refusing to test an MSI that is not explicitly marked unsigned-test-only"
}

$msiexec = Join-Path $env:SystemRoot "System32\msiexec.exe"
$installDir = Join-Path $env:ProgramFiles "Content Masking Tool\maskingtool-server"
$exe = Join-Path $installDir "maskingtool-server.exe"
$sentinelDir = Join-Path $env:APPDATA "ContentMaskingTool"
$testId = [guid]::NewGuid().ToString("N")
$sentinel = Join-Path $sentinelDir "installer-data-retention-sentinel-$testId.txt"
$installLog = Join-Path $env:TEMP "cmt-msi-install-$testId.log"
$repeatLog = Join-Path $env:TEMP "cmt-msi-repeat-$testId.log"
$uninstallLog = Join-Path $env:TEMP "cmt-msi-uninstall-$testId.log"
$installed = $false

function Invoke-Msi([string]$Arguments, [string]$Operation) {
    $process = Start-Process -FilePath $msiexec -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010)) {
        throw "$Operation failed with Windows Installer exit code $($process.ExitCode)"
    }
    if ($process.ExitCode -eq 3010) {
        Write-Host "$Operation requested restart (3010)" -ForegroundColor Yellow
    }
}

New-Item -ItemType Directory -Force -Path $sentinelDir | Out-Null
Set-Content -LiteralPath $sentinel -Value "preserve-$testId" -Encoding ascii

try {
    Invoke-Msi "/i `"$MsiPath`" /qn /norestart /log `"$installLog`"" "install"
    $installed = $true
    if (-not (Test-Path -LiteralPath (Join-Path $installDir "_internal"))) {
        throw "Installed MSI payload is missing _internal"
    }
    $versionOutput = (& $exe --version | Out-String).Trim()
    $expectedVersion = "maskingtool-server $($metadata.version)"
    if ($versionOutput -cne $expectedVersion) {
        throw "Version probe mismatch: expected '$expectedVersion', got '$versionOutput'"
    }

    Invoke-Msi "/i `"$MsiPath`" /qn /norestart /log `"$repeatLog`"" "repeat install"

    $arp = Get-ItemProperty `
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.PSChildName.Trim('{}') -ieq $metadata.productCode.Trim('{}') } |
        Select-Object -First 1
    if (-not $arp) { throw "MSI registration was not found in HKLM uninstall data" }
    if ([string]$arp.DisplayVersion -cne [string]$metadata.version) {
        throw "ARP DisplayVersion does not match installer metadata"
    }

    Invoke-Msi "/x $($metadata.productCode) /qn /norestart /log `"$uninstallLog`"" "uninstall"
    $installed = $false
    if (Test-Path -LiteralPath $installDir) { throw "Managed install directory remains after uninstall" }
    if (-not (Test-Path -LiteralPath $sentinel)) { throw "Per-user data sentinel was removed" }
}
finally {
    if ($installed) {
        try { Invoke-Msi "/x $($metadata.productCode) /qn /norestart" "cleanup uninstall" } catch {}
    }
    Remove-Item -LiteralPath $sentinel -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $installLog,$repeatLog,$uninstallLog -Force -ErrorAction SilentlyContinue
}

Write-Host "MSI lifecycle smoke test passed" -ForegroundColor Green
