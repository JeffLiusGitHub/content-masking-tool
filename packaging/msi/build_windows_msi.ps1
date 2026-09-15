param(
    [string]$PayloadDir,
    [string]$Version,
    [string]$OutputDir,
    [switch]$TestOnly
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if (-not $TestOnly) {
    throw "Formal MSI creation is disabled until production identity and signing are configured. Use -TestOnly."
}
if (-not $PayloadDir) {
    $PayloadDir = Join-Path $root "dist\pyinstaller\maskingtool-server"
}
if (-not $OutputDir) {
    $OutputDir = Join-Path $root "dist"
}
if (-not $Version) {
    $projectText = Get-Content -LiteralPath (Join-Path $root "pyproject.toml") -Raw
    $versionMatch = [regex]::Match($projectText, '(?m)^version\s*=\s*"([^"]+)"')
    if (-not $versionMatch.Success) { throw "Unable to read project version" }
    $Version = $versionMatch.Groups[1].Value
}

$pythonCandidates = @(
    (Join-Path $root ".build-venv\Scripts\python.exe"),
    (Join-Path $root ".venv\Scripts\python.exe")
)
$python = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $python) { throw "Python 3 environment not found; run the frozen build first" }
if (-not (Test-Path -LiteralPath (Join-Path $PayloadDir "maskingtool-server.exe"))) {
    throw "Frozen payload not found: $PayloadDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $PayloadDir "_internal"))) {
    throw "Frozen payload is incomplete: _internal is missing"
}

$toolManifest = Join-Path $root ".config\dotnet-tools.json"
& dotnet tool restore --tool-manifest $toolManifest
if ($LASTEXITCODE -ne 0) { throw "WiX 4 tool restore failed" }

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$workDir = Join-Path $OutputDir "build-msi"
New-Item -ItemType Directory -Force -Path $workDir | Out-Null
$wxs = Join-Path $workDir "content-masking-tool.generated.wxs"
$metadata = Join-Path $OutputDir "content-masking-tool-windows-x64-$Version-unsigned-test-only.json"
$msi = Join-Path $OutputDir "content-masking-tool-windows-x64-$Version-unsigned-test-only.msi"

# This identity is deliberately test-only and must never be reused for a formal MSI.
$testManufacturer = "UNSIGNED TEST ONLY - Content Masking Tool"
$testUpgradeCode = "{E63074D2-2E07-5A50-A16C-8E5B94A6A94A}"

& $python (Join-Path $PSScriptRoot "generate_wxs.py") `
    --payload-dir $PayloadDir `
    --output $wxs `
    --metadata $metadata `
    --version $Version `
    --manufacturer $testManufacturer `
    --upgrade-code $testUpgradeCode
if ($LASTEXITCODE -ne 0) { throw "WiX source generation failed" }

Push-Location -LiteralPath $root
try {
    & dotnet tool run wix -- build `
        -arch x64 `
        -pdbtype none `
        $wxs `
        -out $msi
    if ($LASTEXITCODE -ne 0) { throw "WiX 4 MSI build failed" }
}
finally {
    Pop-Location
}
if (-not (Test-Path -LiteralPath $msi)) { throw "MSI was not produced: $msi" }

Write-Host "Unsigned test MSI: $msi" -ForegroundColor Green
Write-Host "Metadata         : $metadata" -ForegroundColor Green
