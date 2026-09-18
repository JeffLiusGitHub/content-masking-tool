param(
    [Parameter(Mandatory = $true)]
    [string]$SetupPath,
    [Parameter(Mandatory = $true)]
    [string]$MetadataPath,
    [Parameter(Mandatory = $true)]
    [string]$MsiMetadataPath
)

$ErrorActionPreference = "Stop"
$metadata = Get-Content -LiteralPath $MetadataPath -Raw | ConvertFrom-Json
$msiMetadata = Get-Content -LiteralPath $MsiMetadataPath -Raw | ConvertFrom-Json
if ($metadata.testOnly -ne $true) { throw "Refusing to test an unlabelled bootstrapper" }
if ($metadata.version -cne $msiMetadata.version) { throw "Bootstrapper/MSI version mismatch" }
if ($metadata.silentInstallRegistersClaudeExtension -ne $false) {
    throw "Silent setup must not claim to register a Claude extension"
}

$installDir = Join-Path $env:ProgramFiles "Content Masking Tool"
$server = Join-Path $installDir "maskingtool-server\maskingtool-server.exe"
$extension = Join-Path $installDir "Claude Extension\content-masking-tool-win.mcpb"
$userData = Join-Path $env:APPDATA "ContentMaskingTool\vaults"
$sentinel = Join-Path $userData "bootstrapper-test-sentinel.txt"
$runId = [guid]::NewGuid().ToString("N")
$installLog = Join-Path $env:TEMP "content-masking-tool-bootstrapper-install-$runId.log"
$uninstallLog = Join-Path $env:TEMP "content-masking-tool-bootstrapper-uninstall-$runId.log"
$installed = $false

function Invoke-Bundle([string]$Arguments, [string]$Operation) {
    $process = Start-Process -FilePath $SetupPath -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010, 1641)) {
        throw "$Operation failed with exit code $($process.ExitCode)"
    }
}

New-Item -ItemType Directory -Force -Path $userData | Out-Null
Set-Content -LiteralPath $sentinel -Value "preserve" -Encoding utf8NoBOM

try {
    Invoke-Bundle "/install /quiet /norestart /log `"$installLog`"" "bootstrapper install"
    $installed = $true
    if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
        throw "Installed MCP server is missing"
    }
    if (-not (Test-Path -LiteralPath $extension -PathType Leaf)) {
        throw "Staged Claude MCPB is missing"
    }
    $versionOutput = (& $server --version | Out-String).Trim()
    if ($versionOutput -cne "maskingtool-server $($metadata.version)") {
        throw "Installed server version mismatch: $versionOutput"
    }

    $bundleArp = Get-ItemProperty `
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -ceq "Content Masking Tool Setup (Test Only)" } |
        Select-Object -First 1
    if (-not $bundleArp) { throw "Bootstrapper ARP registration was not found" }
    if ([string]$bundleArp.DisplayVersion -cne [string]$metadata.version) {
        throw "Bootstrapper ARP version mismatch"
    }

    $childArp = Get-ItemProperty `
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.PSChildName.Trim('{}') -ieq $msiMetadata.productCode.Trim('{}') } |
        Select-Object -First 1
    if (-not $childArp -or [int]$childArp.SystemComponent -ne 1) {
        throw "Chained MSI is not hidden behind the bootstrapper ARP entry"
    }

    Invoke-Bundle "/uninstall /quiet /norestart /log `"$uninstallLog`"" "bootstrapper uninstall"
    $installed = $false
    if (Test-Path -LiteralPath $installDir) { throw "Install directory remains after uninstall" }
    if (-not (Test-Path -LiteralPath $sentinel)) { throw "Per-user data sentinel was removed" }
}
finally {
    if ($installed) {
        try { Invoke-Bundle "/uninstall /quiet /norestart" "cleanup uninstall" } catch {}
    }
    Remove-Item -LiteralPath $sentinel -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $installLog,$uninstallLog -Force -ErrorAction SilentlyContinue
}

Write-Host "Bootstrapper lifecycle smoke test passed" -ForegroundColor Green
