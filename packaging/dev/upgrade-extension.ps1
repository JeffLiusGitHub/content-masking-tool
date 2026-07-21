# In-place upgrade of the Content Masking Tool extension to the production
# build, bypassing the stuck Settings->Extensions UI.
# Run ONLY while Claude Desktop is fully quit.

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$extensionId = "local.mcpb.jeff-liu.content-masking-tool"
$storeClaudeRoot = Join-Path $env:LOCALAPPDATA "Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
$classicClaudeRoot = Join-Path $env:APPDATA "Claude"
$claudeRoot = if (Test-Path $storeClaudeRoot) { $storeClaudeRoot } else { $classicClaudeRoot }
$extDir = Join-Path $claudeRoot "Claude Extensions\$extensionId"
$stage = Join-Path $root "dist\mcpb-win"

if (Get-Process -Name "Claude" -ErrorAction SilentlyContinue) {
    Write-Host "Claude Desktop is still running. Quit it first (tray icon -> Quit), then run this again." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if (-not (Test-Path (Join-Path $stage "manifest.json"))) {
    Write-Host "Staging payload not found at $stage - run the build first." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

# backup the old (dev) extension, then replace contents with v1.0.0
$backup = Join-Path $root "dist\backup-dev-extension"
if (Test-Path $extDir) {
    if (Test-Path $backup) { Remove-Item $backup -Recurse -Force }
    Move-Item $extDir $backup
}
New-Item -ItemType Directory -Force $extDir | Out-Null
Copy-Item (Join-Path $stage "manifest.json") $extDir
Copy-Item (Join-Path $stage "server") (Join-Path $extDir "server") -Recurse

$manifest = Get-Content (Join-Path $extDir "manifest.json") -Raw | ConvertFrom-Json
$installationsPath = Join-Path $claudeRoot "extensions-installations.json"
$bundlePath = Join-Path $root "dist\content-masking-tool-win.mcpb"
if (Test-Path $installationsPath) {
    $installations = Get-Content $installationsPath -Raw | ConvertFrom-Json
    $record = $installations.extensions.$extensionId
    if ($null -ne $record) {
        $record.version = $manifest.version
        $record.hash = (Get-FileHash $bundlePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $record.manifest = $manifest
        $installations | ConvertTo-Json -Depth 20 | Set-Content $installationsPath -Encoding UTF8
    }
}
Write-Host ""
Write-Host ("Upgraded to version {0}. Old dev extension backed up to dist\backup-dev-extension." -f $manifest.version) -ForegroundColor Green
Write-Host "Now start Claude Desktop and check Connectors for Content Masking Tool v1.0.0." -ForegroundColor Green
Read-Host "Press Enter to close"
