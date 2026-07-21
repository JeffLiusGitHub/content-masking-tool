# PreToolUse hook: HARD-BLOCK direct reads of document formats that must go
# through the masking tool. Executed by the Claude Code harness (not the
# model), so this is deterministic enforcement, not advisory guidance.
$stdin = [Console]::In.ReadToEnd()
try { $payload = $stdin | ConvertFrom-Json } catch { exit 0 }

$filePath = $payload.tool_input.file_path
if (-not $filePath) { exit 0 }

# .md left unblocked intentionally: masked output files are .md and this
# project's own docs are .md — see USAGE.md "enforced vs not enforceable"
if ($filePath -match '\.(pdf|docx|doc)$') {
    [Console]::Error.WriteLine(
        "BLOCKED by masking policy: document files must never be read directly. " +
        "Use the content-masking-tool MCP server instead: call mask_document " +
        "with file_path='$filePath' and work with the masked text it returns."
    )
    exit 2
}
exit 0
