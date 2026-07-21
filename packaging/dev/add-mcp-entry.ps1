# Adds the content-masking-tool MCP server entry to Claude Desktop's config.
# Run this ONLY while Claude Desktop is fully quit — the app rewrites the
# config file from memory and will clobber external edits made while it runs.

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$configPath = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"

if (Get-Process -Name "Claude" -ErrorAction SilentlyContinue) {
    Write-Host "Claude Desktop is still running. Quit it first (tray icon -> Quit), then run this again." -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}

if (Test-Path $configPath) {
    $config = Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
} else {
    # Claude Desktop removes the file on quit sometimes; start a fresh one —
    # the app merges its own settings back in on next launch
    New-Item -ItemType Directory -Force (Split-Path $configPath) | Out-Null
    $config = [PSCustomObject]@{}
}

if (-not ($config.PSObject.Properties.Name -contains "mcpServers")) {
    $config | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([PSCustomObject]@{})
}

$entry = [PSCustomObject]@{
    command = Join-Path $root ".venv\Scripts\python.exe"
    args    = @("-m", "maskingtool.mcp_server.server")
}

if ($config.mcpServers.PSObject.Properties.Name -contains "content-masking-tool") {
    $config.mcpServers."content-masking-tool" = $entry
} else {
    $config.mcpServers | Add-Member -MemberType NoteProperty -Name "content-masking-tool" -Value $entry
}

# Back up an existing config, then write UTF-8 without BOM.
# On some Claude Desktop versions the config is removed during shutdown, so
# there may be nothing to back up on the first run.
if (Test-Path $configPath) {
    Copy-Item $configPath "$configPath.backup" -Force
}
$json = $config | ConvertTo-Json -Depth 32
[System.IO.File]::WriteAllText($configPath, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Done. MCP entry added. Backup saved as claude_desktop_config.json.backup" -ForegroundColor Green
Write-Host "Now start Claude Desktop and follow TESTING_GUIDE.md step 3." -ForegroundColor Green
Read-Host "Press Enter to close"
