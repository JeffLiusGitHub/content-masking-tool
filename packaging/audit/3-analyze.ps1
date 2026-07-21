# Summarize the captured network verdicts into a human-readable report +
# screenshot-ready console table. Run after the capture (any time).
$here = $PSScriptRoot
$jsonl = Join-Path $here "audit-network.jsonl"
if (-not (Test-Path $jsonl)) { Write-Host "No capture found at $jsonl" -ForegroundColor Red; exit 1 }

$rows = @(Get-Content $jsonl | ForEach-Object { $_ | ConvertFrom-Json })
$anthropic = @($rows | Where-Object { $_.host -match "anthropic|claude" })
$leaks = @($anthropic | Where-Object { -not $_.clean })

Write-Host ""
Write-Host "=== Network audit summary ===" -ForegroundColor Cyan
Write-Host ("Requests to Anthropic/Claude hosts : {0}" -f $anthropic.Count)
Write-Host ("Requests carrying a sentinel (LEAK): {0}" -f $leaks.Count) -ForegroundColor $(if ($leaks.Count) { "Red" } else { "Green" })
Write-Host ""
$anthropic | Select-Object timestamp, host, path, body_bytes, clean, @{n="leaked";e={$_.leaked_sentinels -join ","}} | Format-Table -AutoSize

$verdict = if ($leaks.Count -eq 0) { "PASS: no sentinel (original name) crossed the wire to Anthropic" }
           else { "FAIL: $($leaks.Count) request(s) leaked a sentinel" }
Write-Host $verdict -ForegroundColor $(if ($leaks.Count) { "Red" } else { "Green" })
$verdict | Out-File (Join-Path $here "network-audit-verdict.txt") -Encoding utf8
