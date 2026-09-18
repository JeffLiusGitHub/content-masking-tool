param(
    [string]$MsiPath,
    [string]$MsiMetadataPath,
    [string]$Version,
    [string]$OutputDir,
    [string]$SigningCertificateThumbprint,
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$TestOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $TestOnly) {
    throw "Formal bootstrapper creation is disabled until production identities and signing are configured. Use -TestOnly."
}
if (-not $OutputDir) { $OutputDir = Join-Path $root "dist" }
if (-not $Version) {
    $projectText = Get-Content -LiteralPath (Join-Path $root "pyproject.toml") -Raw
    $versionMatch = [regex]::Match($projectText, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $versionMatch.Success) { throw "Unable to read project version" }
    $Version = $versionMatch.Groups[1].Value
}
if (-not $MsiPath) {
    $matches = @(Get-ChildItem -LiteralPath $OutputDir -Filter "content-masking-tool-windows-x64-$Version-unsigned-test-only.msi")
    if ($matches.Count -ne 1) { throw "Expected exactly one MSI for version $Version" }
    $MsiPath = $matches[0].FullName
}
if (-not $MsiMetadataPath) {
    $MsiMetadataPath = Join-Path $OutputDir "content-masking-tool-windows-x64-$Version-unsigned-test-only.json"
}
if (-not (Test-Path -LiteralPath $MsiPath -PathType Leaf)) { throw "MSI not found: $MsiPath" }
if (-not (Test-Path -LiteralPath $MsiMetadataPath -PathType Leaf)) { throw "MSI metadata not found: $MsiMetadataPath" }

$msiMetadata = Get-Content -LiteralPath $MsiMetadataPath -Raw | ConvertFrom-Json
if ($msiMetadata.version -cne $Version) { throw "MSI metadata version does not match $Version" }
if ($msiMetadata.testOnly -ne $true) { throw "Bootstrapper test build requires a test-only MSI" }
if ($msiMetadata.claudeExtensionIncluded -ne $true) {
    throw "MSI must include the Claude MCPB before creating the bootstrapper"
}

$pythonCandidates = @(
    (Join-Path $root ".build-venv\Scripts\python.exe"),
    (Join-Path $root ".venv\Scripts\python.exe")
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) { $python = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $python) { throw "Python 3 environment not found" }

$toolManifest = Join-Path $root ".config\dotnet-tools.json"
& dotnet tool restore --tool-manifest $toolManifest
if ($LASTEXITCODE -ne 0) { throw "WiX 4 tool restore failed" }
& dotnet tool run wix -- extension add -g WixToolset.Bal.wixext/4.0.6
if ($LASTEXITCODE -ne 0) { throw "WiX Bal extension restore failed" }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$workDir = Join-Path $OutputDir "build-bootstrapper"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$wxs = Join-Path $workDir "content-masking-tool-bootstrapper.generated.wxs"
$artifactLabel = if ($SigningCertificateThumbprint) { "self-signed-test-only" } else { "unsigned-test-only" }
$metadata = Join-Path $OutputDir "content-masking-tool-windows-x64-$Version-bootstrapper-$artifactLabel.json"
$setup = Join-Path $OutputDir "content-masking-tool-windows-x64-$Version-bootstrapper-$artifactLabel.exe"
$msiForBundle = (Resolve-Path -LiteralPath $MsiPath).Path

# This identity is deliberately test-only and must never be reused for a formal bundle.
$testManufacturer = "UNSIGNED TEST ONLY - Content Masking Tool"
$testBundleUpgradeCode = "{9F7440DA-287A-5D3D-B937-D757302FF201}"

if ($SigningCertificateThumbprint) {
    $signTool = Get-ChildItem -LiteralPath "${env:ProgramFiles(x86)}\Windows Kits\10\bin" `
        -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*\x64\signtool.exe" } |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if (-not $signTool) { throw "signtool.exe was not found" }
    $signedMsi = Join-Path $OutputDir "content-masking-tool-windows-x64-$Version-self-signed-test-only.msi"
    Copy-Item -LiteralPath $MsiPath -Destination $signedMsi -Force
    & $signTool.FullName sign /fd SHA256 /sha1 $SigningCertificateThumbprint `
        /tr $TimestampUrl /td SHA256 /d "Content Masking Tool $Version SELF-SIGNED TEST ONLY" `
        $signedMsi
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $signedMsi" }
    $msiForBundle = $signedMsi
}

Push-Location -LiteralPath $root
try {
    & $python (Join-Path $PSScriptRoot "generate_bundle_wxs.py") `
        --msi $msiForBundle `
        --output $wxs `
        --metadata $metadata `
        --version $Version `
        --manufacturer $testManufacturer `
        --upgrade-code $testBundleUpgradeCode `
        --signing-mode $artifactLabel
    if ($LASTEXITCODE -ne 0) { throw "Bootstrapper source generation failed" }

    & dotnet tool run wix -- build `
        -arch x64 `
        -ext WixToolset.Bal.wixext `
        -pdbtype none `
        $wxs `
        -out $setup
    if ($LASTEXITCODE -ne 0) { throw "WiX 4 bootstrapper build failed" }
}
finally {
    Pop-Location
}
if (-not (Test-Path -LiteralPath $setup -PathType Leaf)) {
    throw "Bootstrapper was not produced: $setup"
}

if ($SigningCertificateThumbprint) {
    & $signTool.FullName sign /fd SHA256 /sha1 $SigningCertificateThumbprint `
        /tr $TimestampUrl /td SHA256 /d "Content Masking Tool $Version SELF-SIGNED TEST ONLY" `
        $setup
    if ($LASTEXITCODE -ne 0) { throw "Signing failed: $setup" }
}

Write-Host "Test bootstrapper: $setup" -ForegroundColor Green
Write-Host "Metadata         : $metadata" -ForegroundColor Green
