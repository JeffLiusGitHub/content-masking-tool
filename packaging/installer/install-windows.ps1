# One-click installer: Content Masking Tool
#
# Installs the tool for BOTH Claude clients in one run:
#   1. Claude Desktop — extracts the .mcpb payload into the app's extension
#      directory and registers it in extensions-installations.json
#      (same mechanism as packaging\dev\upgrade-extension.ps1).
#   2. Claude Code   — registers a user-scoped MCP entry via `claude mcp add`
#      pointing at the exe installed in step 1 (skipped when the CLI is absent).
#
# Payload: content-masking-tool-win.mcpb sitting NEXT TO this script
# (falls back to ..\..\dist\ when run from a repo checkout).
# Run via install.bat (double-click) or:
#   powershell -ExecutionPolicy Bypass -File install-windows.ps1

$ErrorActionPreference = "Stop"

# --- locate payload -----------------------------------------------------
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$mcpb = Join-Path $here "content-masking-tool-win.mcpb"
if (-not (Test-Path $mcpb)) {
    $mcpb = Join-Path $here "..\..\dist\content-masking-tool-win.mcpb"
}
if (-not (Test-Path $mcpb)) {
    Write-Host "content-masking-tool-win.mcpb not found next to this script." -ForegroundColor Red
    exit 1
}
$mcpb = (Resolve-Path $mcpb).Path
Write-Host "Payload: $mcpb"

# --- locate Claude Desktop ----------------------------------------------
$storeRoot = Join-Path $env:LOCALAPPDATA "Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude"
$classicRoot = Join-Path $env:APPDATA "Claude"
$claudeRoot = $null
if (Test-Path $storeRoot) { $claudeRoot = $storeRoot }
elseif (Test-Path $classicRoot) { $claudeRoot = $classicRoot }

$extensionId = "local.mcpb.jeff-liu.content-masking-tool"
$extExe = $null

if ($null -eq $claudeRoot) {
    Write-Host "Claude Desktop not found - skipping the Desktop extension step." -ForegroundColor Yellow
} else {
    # The app rewrites its state files from memory on quit; installing while
    # it runs would be silently clobbered.
    while (Get-Process -Name "Claude" -ErrorAction SilentlyContinue) {
        Write-Host "Claude Desktop is running. Quit it (tray icon -> Quit), then press Enter." -ForegroundColor Yellow
        Read-Host | Out-Null
    }

    # extract the .mcpb (a zip) into the extension directory
    $extDir = Join-Path $claudeRoot "Claude Extensions\$extensionId"
    $stage = Join-Path $env:TEMP ("cmt-install-" + [guid]::NewGuid().ToString("N"))
    $zipCopy = "$stage.zip"
    Copy-Item $mcpb $zipCopy
    Expand-Archive -Path $zipCopy -DestinationPath $stage
    Remove-Item $zipCopy

    if (Test-Path $extDir) {
        $backup = "$extDir.previous"
        if (Test-Path $backup) { Remove-Item $backup -Recurse -Force }
        Move-Item $extDir $backup
        Write-Host "Previous install backed up to: $backup"
    }
    New-Item -ItemType Directory -Force (Split-Path $extDir) | Out-Null
    Move-Item $stage $extDir

    # register (or update) the installation record
    $manifest = Get-Content (Join-Path $extDir "manifest.json") -Raw | ConvertFrom-Json
    $installationsPath = Join-Path $claudeRoot "extensions-installations.json"
    if (Test-Path $installationsPath) {
        $installations = Get-Content $installationsPath -Raw | ConvertFrom-Json
    } else {
        $installations = [PSCustomObject]@{ extensions = [PSCustomObject]@{} }
    }
    if (-not ($installations.PSObject.Properties.Name -contains "extensions")) {
        $installations | Add-Member -MemberType NoteProperty -Name "extensions" -Value ([PSCustomObject]@{})
    }
    $record = [PSCustomObject]@{
        id            = $extensionId
        version       = $manifest.version
        hash          = (Get-FileHash $mcpb -Algorithm SHA256).Hash.ToLowerInvariant()
        installedAt   = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ss.fffZ")
        manifest      = $manifest
        signatureInfo = [PSCustomObject]@{ status = "unsigned" }
        source        = "local"
    }
    if ($installations.extensions.PSObject.Properties.Name -contains $extensionId) {
        $record.installedAt = $installations.extensions.$extensionId.installedAt
        $installations.extensions.$extensionId = $record
    } else {
        $installations.extensions | Add-Member -MemberType NoteProperty -Name $extensionId -Value $record
    }
    $json = $installations | ConvertTo-Json -Depth 32
    [System.IO.File]::WriteAllText($installationsPath, $json, (New-Object System.Text.UTF8Encoding($false)))

    $extExe = Join-Path $extDir "server\maskingtool-server\maskingtool-server.exe"
    Write-Host ("Claude Desktop: extension v{0} installed." -f $manifest.version) -ForegroundColor Green
}

# --- register with Claude Code ------------------------------------------
if ($null -eq $extExe) {
    # No Claude Desktop: unpack the server beside this script so Claude Code
    # still gets a working binary.
    $extDir = Join-Path $here "maskingtool"
    if (-not (Test-Path (Join-Path $extDir "server\maskingtool-server\maskingtool-server.exe"))) {
        $stage = Join-Path $env:TEMP ("cmt-install-" + [guid]::NewGuid().ToString("N"))
        $zipCopy = "$stage.zip"
        Copy-Item $mcpb $zipCopy
        Expand-Archive -Path $zipCopy -DestinationPath $stage
        Remove-Item $zipCopy
        if (Test-Path $extDir) { Remove-Item $extDir -Recurse -Force }
        Move-Item $stage $extDir
    }
    $extExe = Join-Path $extDir "server\maskingtool-server\maskingtool-server.exe"
    Write-Host "Server binary unpacked to: $extExe"
}

$claudeCli = Get-Command claude -ErrorAction SilentlyContinue
if ($null -eq $claudeCli) {
    Write-Host "Claude Code CLI not found - skipped. To register later, run:" -ForegroundColor Yellow
    Write-Host "  claude mcp add --scope user content-masking-tool -- `"$extExe`""
} else {
    claude mcp remove --scope user content-masking-tool 2>$null | Out-Null
    claude mcp add --scope user content-masking-tool -- "$extExe"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Claude Code: user-scoped MCP entry registered." -ForegroundColor Green
    } else {
        Write-Host "Claude Code registration failed - run manually:" -ForegroundColor Yellow
        Write-Host "  claude mcp add --scope user content-masking-tool -- `"$extExe`""
    }
}

Write-Host ""
Write-Host "Done. Start Claude Desktop and check Settings -> Extensions." -ForegroundColor Green
Write-Host "Masked files will be created in Documents\Masked Files." -ForegroundColor Green
