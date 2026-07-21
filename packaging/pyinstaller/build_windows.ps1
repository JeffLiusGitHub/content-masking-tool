# Build the frozen Windows MCP server + production release artifacts.
# Run from anywhere: paths resolve relative to this script.
# Clean-machine prerequisites: uv and Node.js/npm on PATH.

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$distRoot = Join-Path $root "dist"
$mcpbRoot = Join-Path $root "packaging\mcpb"
$buildVenv = Join-Path $root ".build-venv"
$python = Join-Path $buildVenv "Scripts\python.exe"

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    throw "uv is required. Install it from https://astral.sh/uv"
}
$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    throw "Node.js/npm is required to pack the MCPB extension."
}
$tarCommand = Get-Command tar.exe -ErrorAction SilentlyContinue
if (-not $tarCommand) {
    throw "Windows tar.exe is required to create the standalone ZIP."
}

Write-Host "== 1/9 Install locked Python dependencies ==" -ForegroundColor Cyan
$env:UV_PROJECT_ENVIRONMENT = $buildVenv
& $uvCommand.Source sync --project $root --locked --extra dev
if ($LASTEXITCODE -ne 0) { throw "uv sync failed" }
if (-not (Test-Path -LiteralPath $python)) { throw "project Python not found: $python" }

Write-Host "== 2/9 Install locked MCPB packer ==" -ForegroundColor Cyan
Push-Location -LiteralPath $mcpbRoot
try {
    & $npmCommand.Source ci --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm ci failed" }
}
finally {
    Pop-Location
}
$mcpb = Join-Path $mcpbRoot "node_modules\.bin\mcpb.cmd"
if (-not (Test-Path -LiteralPath $mcpb)) { throw "locked MCPB CLI not found: $mcpb" }

Write-Host "== 3/9 Validate release metadata ==" -ForegroundColor Cyan
& $python (Join-Path $root "packaging\check_release_metadata.py")
if ($LASTEXITCODE -ne 0) { throw "release metadata validation failed" }

Write-Host "== 4/9 Run source test suite ==" -ForegroundColor Cyan
& $python -m pytest
if ($LASTEXITCODE -ne 0) { throw "source tests failed" }

Write-Host "== 5/9 PyInstaller build (onedir) ==" -ForegroundColor Cyan
& $python -m PyInstaller --clean --noconfirm `
    --distpath (Join-Path $distRoot "pyinstaller") `
    --workpath (Join-Path $distRoot "build") `
    (Join-Path $PSScriptRoot "maskingtool.spec")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$bundle = Join-Path $distRoot "pyinstaller\maskingtool-server"
$exe = Join-Path $bundle "maskingtool-server.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "frozen exe not found: $exe" }

Write-Host "== 6/9 Smoke test frozen MCP stdio server ==" -ForegroundColor Cyan
& $python (Join-Path $PSScriptRoot "smoke_frozen.py") $exe
if ($LASTEXITCODE -ne 0) { throw "frozen exe smoke test failed" }

Write-Host "== 7/9 Assemble production MCPB payload ==" -ForegroundColor Cyan
$stage = Join-Path $distRoot "mcpb-win"
if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
New-Item -ItemType Directory -Force (Join-Path $stage "server") | Out-Null
Copy-Item -LiteralPath $bundle -Destination (Join-Path $stage "server\maskingtool-server") -Recurse
Copy-Item -LiteralPath (Join-Path $mcpbRoot "manifest.json") -Destination $stage

Write-Host "== 8/9 Pack MCPB ==" -ForegroundColor Cyan
$mcpbPackage = Join-Path $distRoot "content-masking-tool-win.mcpb"
& $mcpb pack $stage $mcpbPackage
if ($LASTEXITCODE -ne 0) { throw "mcpb pack failed" }

Write-Host "== 9/9 Create standalone ZIP and checksums ==" -ForegroundColor Cyan
$cliZip = Join-Path $distRoot "maskingtool-windows-standalone.zip"
if (Test-Path -LiteralPath $cliZip) { Remove-Item -LiteralPath $cliZip -Force }
& $tarCommand.Source -a -c -f $cliZip `
    -C (Split-Path -Parent $bundle) `
    (Split-Path -Leaf $bundle)
if ($LASTEXITCODE -ne 0) { throw "standalone ZIP creation failed" }

$checksumFile = Join-Path $distRoot "SHA256SUMS-windows.txt"
$checksumLines = foreach ($artifact in @($mcpbPackage, $cliZip)) {
    $hash = (Get-FileHash -LiteralPath $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $([System.IO.Path]::GetFileName($artifact))"
}
$checksumLines | Set-Content -LiteralPath $checksumFile -Encoding ascii

Write-Host "`nDone:" -ForegroundColor Green
Write-Host "  MCP extension : $mcpbPackage" -ForegroundColor Green
Write-Host "  Standalone CLI: $cliZip" -ForegroundColor Green
Write-Host "  Checksums     : $checksumFile" -ForegroundColor Green
