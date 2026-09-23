param(
    [Parameter(Mandatory = $true)][string]$OldSetupPath,
    [Parameter(Mandatory = $true)][string]$OldMetadataPath,
    [Parameter(Mandatory = $true)][string]$OldMsiMetadataPath,
    [Parameter(Mandatory = $true)][string]$NewSetupPath,
    [Parameter(Mandatory = $true)][string]$NewMetadataPath,
    [Parameter(Mandatory = $true)][string]$NewMsiMetadataPath
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Bootstrapper upgrade test requires an elevated/administrator runner"
}

$OldSetupPath = (Resolve-Path -LiteralPath $OldSetupPath).Path
$NewSetupPath = (Resolve-Path -LiteralPath $NewSetupPath).Path
$oldMetadata = Get-Content -LiteralPath $OldMetadataPath -Raw | ConvertFrom-Json
$oldMsiMetadata = Get-Content -LiteralPath $OldMsiMetadataPath -Raw | ConvertFrom-Json
$newMetadata = Get-Content -LiteralPath $NewMetadataPath -Raw | ConvertFrom-Json
$newMsiMetadata = Get-Content -LiteralPath $NewMsiMetadataPath -Raw | ConvertFrom-Json

foreach ($metadata in @($oldMetadata, $oldMsiMetadata, $newMetadata, $newMsiMetadata)) {
    if ($metadata.testOnly -ne $true) {
        throw "Upgrade acceptance only permits explicitly test-only packages"
    }
}
if ([version]$oldMetadata.version -ge [version]$newMetadata.version) {
    throw "New bundle version must be greater than the old bundle version"
}
if ($oldMetadata.version -cne $oldMsiMetadata.version -or
    $newMetadata.version -cne $newMsiMetadata.version) {
    throw "Bundle/MSI metadata versions do not agree"
}
if ($oldMetadata.bundleUpgradeCode -cne $newMetadata.bundleUpgradeCode) {
    throw "Burn bundle UpgradeCode changed across versions"
}
if ($oldMsiMetadata.upgradeCode -cne $newMsiMetadata.upgradeCode) {
    throw "MSI UpgradeCode changed across versions"
}
if ($oldMsiMetadata.productCode -ceq $newMsiMetadata.productCode) {
    throw "MSI ProductCode did not change for the new version"
}

$installDir = Join-Path $env:ProgramFiles "Content Masking Tool"
$server = Join-Path $installDir "maskingtool-server\maskingtool-server.exe"
$appDataRoot = Join-Path $env:APPDATA "ContentMaskingTool"
$settingsPath = Join-Path $appDataRoot "settings.json"
$vaultDir = Join-Path $appDataRoot "vaults"
$testId = [guid]::NewGuid().ToString("N")
$vaultSentinel = Join-Path $vaultDir "upgrade-test-sentinel-$testId.json"
$oldInstallLog = Join-Path $env:TEMP "cmt-upgrade-old-install-$testId.log"
$upgradeLog = Join-Path $env:TEMP "cmt-upgrade-new-install-$testId.log"
$uninstallLog = Join-Path $env:TEMP "cmt-upgrade-new-uninstall-$testId.log"
$oldInstalled = $false
$newInstalled = $false

if (Test-Path -LiteralPath $settingsPath) {
    throw "Upgrade test requires a clean runner with no existing settings.json"
}

function Invoke-Bundle(
    [string]$Path,
    [string]$Arguments,
    [string]$Operation
) {
    $process = Start-Process -FilePath $Path -ArgumentList $Arguments -Wait -PassThru
    if ($process.ExitCode -notin @(0, 3010, 1641)) {
        throw "$Operation failed with exit code $($process.ExitCode)"
    }
}

function Assert-Version([string]$Version) {
    if (-not (Test-Path -LiteralPath $server -PathType Leaf)) {
        throw "Installed server is missing"
    }
    $actual = (& $server --version | Out-String).Trim()
    $expected = "maskingtool-server $Version"
    if ($actual -cne $expected) {
        throw "Version probe mismatch: expected '$expected', got '$actual'"
    }
}

function Get-UninstallEntry([string]$ProductCode) {
    return Get-ItemProperty `
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.PSChildName.Trim('{}') -ieq $ProductCode.Trim('{}') } |
        Select-Object -First 1
}

New-Item -ItemType Directory -Force -Path $vaultDir | Out-Null
$settingsJson = '{"enable_ner":false,"ner_backend":"spacy","language":"zh","masked_output_dir":"C:\\Upgrade Test Output"}'
[IO.File]::WriteAllText($settingsPath, $settingsJson, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText($vaultSentinel, '{"preserve":true}', [Text.UTF8Encoding]::new($false))
$settingsHash = (Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash
$vaultHash = (Get-FileHash -LiteralPath $vaultSentinel -Algorithm SHA256).Hash

try {
    Invoke-Bundle $OldSetupPath "/install /quiet /norestart /log `"$oldInstallLog`"" "old bundle install"
    $oldInstalled = $true
    Assert-Version $oldMetadata.version

    Invoke-Bundle $NewSetupPath "/install /quiet /norestart /log `"$upgradeLog`"" "bundle upgrade"
    $newInstalled = $true
    Assert-Version $newMetadata.version

    if ((Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash -cne $settingsHash) {
        throw "settings.json changed during upgrade"
    }
    if ((Get-FileHash -LiteralPath $vaultSentinel -Algorithm SHA256).Hash -cne $vaultHash) {
        throw "Vault sentinel changed during upgrade"
    }
    if (Get-UninstallEntry $oldMsiMetadata.productCode) {
        throw "Old MSI ProductCode remains registered after Major Upgrade"
    }
    $newChildEntry = Get-UninstallEntry $newMsiMetadata.productCode
    if (-not $newChildEntry -or [int]$newChildEntry.SystemComponent -ne 1) {
        throw "New chained MSI is missing or visible in Add/Remove Programs"
    }

    $bundleEntries = @(Get-ItemProperty `
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*', `
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.DisplayName -ceq "Content Masking Tool Setup (Test Only)" })
    if ($bundleEntries.Count -ne 1 -or
        [string]$bundleEntries[0].DisplayVersion -cne [string]$newMetadata.version) {
        throw "Expected exactly one new-version bundle registration after upgrade"
    }

    Invoke-Bundle $NewSetupPath "/uninstall /quiet /norestart /log `"$uninstallLog`"" "new bundle uninstall"
    $newInstalled = $false
    $oldInstalled = $false
    if (Test-Path -LiteralPath $installDir) {
        throw "Managed install directory remains after upgraded bundle uninstall"
    }
    if ((Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash -cne $settingsHash) {
        throw "settings.json changed during uninstall"
    }
    if ((Get-FileHash -LiteralPath $vaultSentinel -Algorithm SHA256).Hash -cne $vaultHash) {
        throw "Vault sentinel changed during uninstall"
    }
}
finally {
    if ($newInstalled) {
        try { Invoke-Bundle $NewSetupPath "/uninstall /quiet /norestart" "new bundle cleanup" } catch {}
    }
    if ($oldInstalled) {
        try { Invoke-Bundle $OldSetupPath "/uninstall /quiet /norestart" "old bundle cleanup" } catch {}
    }
    Remove-Item -LiteralPath $settingsPath,$vaultSentinel -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $oldInstallLog,$upgradeLog,$uninstallLog -Force -ErrorAction SilentlyContinue
}

Write-Host "Bootstrapper upgrade and settings-retention test passed" -ForegroundColor Green
