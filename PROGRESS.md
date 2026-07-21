# Progress — Content Masking Tool (Stage 1)

> Plan: [CLAUDE.md](CLAUDE.md) · Test plan & TDD workflow: [TESTPLAN.md](TESTPLAN.md) · Test evidence: [Test result/README.md](Test%20result/README.md). Update this file as milestones complete.

**Last updated:** 2026-07-21

## Current status

**Clean release-build readiness complete:** Windows and macOS release scripts
now bootstrap an isolated `.build-venv`, install Python and MCPB dependencies
from lockfiles, validate synchronized release metadata, run the full test suite,
build/smoke-test the frozen server, and emit MCPB/ZIP artifacts plus SHA-256
files. MCPB is pinned to 2.1.2. The Windows flow completed end-to-end: 148 tests
passed, frozen smoke passed, MCPB schema validation passed, and both generated
artifact hashes verified. The macOS manifest now exposes the same five review
tools as Windows; the macOS build still requires execution on macOS.

**v1.2.0 GUI implemented:** the Windows standalone executable now selects
between drag-and-drop GUI, CLI, and MCP modes. The GUI includes automatic
mask/restore detection, persistent vault history, safe ambiguity selection,
non-overwriting output names, and a red/green text diff.
Source verification: 119 passed / 3 conditional NER tests skipped. Frozen MCP
smoke and GUI launch smoke passed; Windows standalone ZIP and MCPB rebuilt.

**Bilingual update:** GUI now defaults to English and offers a persistent
English/中文 selector covering the main window, statuses, dialogs, vault picker,
and history window. Verification: 123 passed; frozen artifacts rebuilt.

**Manual review update:** users can select a missed name/company directly in
the diff, classify it as PERSON or ORG, persist it in a dedicated custom-term
list, and re-mask every exact occurrence in the source using the same vault.
Future documents load these terms automatically. Verification: 124 passed;
frozen MCP/GUI smoke tests passed and Windows artifacts rebuilt.

**Milestones 0–8 complete. Full test suite: 103 passed / 0 failed** (TDD red→green per milestone; evidence with screenshots in `Test result/`). Includes scale validation against a representative 63-name list of fictional placeholders (`tests/test_realworld_names.py`) and name-part expansion (`tests/test_name_expansion.py`).

The engine, all three input formats, the CLI, and the MCP server are built and tested. What remains is delivery: Claude Desktop end-to-end verification (M9), then PyInstaller + MCPB packaging (M10 Windows, M11 macOS).

### Next action

M9 — wire the dev-mode server into Claude Desktop (`claude_desktop_config.json` entry pointing at `.venv\Scripts\python.exe -m maskingtool.mcp_server.server`) and run the manual mask → chat → restore checklist from TESTPLAN section 5.

## Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 0 | Dev env: uv + Python 3.11.15 installed | ✅ 2026-07-14 |
| 1 | Project scaffold (pyproject.toml, src layout, deps) | ✅ 2026-07-14 |
| 2 | Core data model: `spans.py` + `vault.py` | ✅ 15/15 tests |
| 3 | Masking engine: `recognizers.py` + `operators.py` + `engine.py` | ✅ 20/20 tests (incl. NER priority) |
| 4 | Markdown parser/renderers + CLI (first runnable milestone) | ✅ 17/17 tests + real CLI demo |
| 5 | DOCX parser + renderer | ✅ 8/8 tests |
| 6 | PDF text extraction (read-only) + scanned-page detection | ✅ 5/5 tests |
| 7 | Deny-list loader + sample CSVs | ✅ 6/6 tests |
| 8 | MCP server: `schemas.py` + `tools.py` + `server.py` | ✅ 8/8 tests (in-memory MCP client) |
| 9 | End-to-end verification in a real Claude conversation | ✅ 2026-07-15 — live E2E via MCP tools (mask → tokens-only in chat → restore_document byte-identical). Note: old `claude_desktop_config.json` dev route is dead on the new app; dev `.mcpb` installs but can't run in cowork VM (absolute host path). See `Test result/M9_claude_desktop/` |
| 10 | PyInstaller + MCPB packaging (Windows) | 🟢 v1.1.0 installed & verified 2026-07-16 — extension upgraded in place (UI was stuck; `upgrade-extension.bat` bypass), live E2E from a real session: mask (15 PERSON + 3 ORG, deny-list + expansion + NER together) → restore_document byte-exact, `unresolved: []`. Artifacts: `.mcpb` (103MB) + `maskingtool-windows-standalone.zip` (dual-mode CLI). **Remaining for sign-off: user chat-window test + clean-machine install** |
| 11 | macOS packaging | Not started |

## Decisions log

- **2026-07-14** — Base engine: Microsoft Presidio (MIT). Deny-list first (deterministic, score 1.0), optional local NER (spaCy/GLiNER) off by default.
- **2026-07-14** — Delivery: MCP server packaged as Claude Desktop Extension (`.mcpb`) with `server.type: "binary"` (PyInstaller-frozen exe per OS).
- **2026-07-14** — Distribution: private/internal only. Platforms: Windows + macOS.
- **2026-07-14** — Restore is regex-based token scan + vault lookup, not Presidio's DeanonymizeEngine.
- **2026-07-14** — Dev environment: uv-managed Python 3.11.15 (machine only had Python 2.7).
- **2026-07-14** — **Privacy-first masking for Markdown**: an earlier spec draft protected code blocks/URLs from masking; that contradicted INV-3 (zero leakage) and lost. Everything is masked — code, URLs, front-matter. TESTPLAN 4.4 amended.
- **2026-07-14** — **Custom deny-list regex instead of Presidio's `deny_list` param**: Presidio's built-in uses `\b` boundaries that fail between CJK characters (Chinese names inside Chinese sentences would be missed). We build per-term patterns: ASCII terms get boundary guards, CJK terms match anywhere.
- **2026-07-14** — **Case-sensitive matching enforced explicitly**: Presidio's `PatternRecognizer` defaults include `re.IGNORECASE`; caught by test, overridden via `global_regex_flags`.
- **2026-07-14** — Replacement is applied by our own span-aware logic (not AnonymizerEngine operators) because entities split across DOCX runs need cross-span handling Presidio doesn't do; Presidio is used for analysis only.
- **2026-07-14** — `MASKINGTOOL_DATA_DIR` env var overrides the app-data location (test isolation; also useful for packaging).
- **2026-07-14** — **Name-part expansion ON by default** (user request): bare first names/surnames from the people list are masked too ("Owen", "Bradley", bare "Sam"). Each distinct string gets its own token and restores to exactly itself — a bare "Sam" is never guessed into a full name. Guards: full names win (longest match), word boundaries hold ("Sam" ≠ "Samuel"), single-letter parts never expanded (the "K" in "Dana K"), CJK names not split, ORG lists never expanded, case-sensitive. Toggle: `expand_person_name_parts` in settings.json / `--no-expand-names` CLI / `expand_name_parts` MCP param. Accepted trade-off: capitalized common-word collisions ("Summer", "Field", "Phoenix") can over-mask at sentence start — recall wins over precision by design.
- **2026-07-14** — **Byte-faithful text IO** (`textio.py`): Python's default newline translation rewrote LF as CRLF on Windows writes, breaking byte-for-byte round-trip. All document reads/writes now use `newline=""`. Caught by the real-world CLI demo's OS-level byte comparison, not by Python-side tests (which translate on read too) — that comparison is now a permanent parametrized test (LF + CRLF).

- **2026-07-16** — **Requirement change (meeting): names will be RANDOM, not from a known list → NER enabled** (`settings.json` `enable_ner: true` on this machine; hot-read per mask call). Architecture unchanged — NER is a detection switch inside the same MCP server; vault/restore/tool interfaces untouched. Deny-list remains highest priority (score 1.0 vs NER ≤0.99) and stays the recommended channel for *known-critical* names since NER is probabilistic. Live-verified: random person + company (incl. "Pty Ltd" suffix) caught; **known gap: Chinese entities missed by the English model** — needs a zh model or GLiNER (Stage 2 decision). M10 packaging must now bundle `en_core_web_sm` (~13MB). INV-3 (zero leakage) remains guaranteed only for deny-listed names; for random names the honest claim is "high recall, not guaranteed".

- **2026-07-16** — **v1.1.0**: (1) Claude Code enforcement hook (`.claude/hooks/enforce-masking.ps1`) hard-blocks direct Read of .pdf/.docx/.doc — deterministic, framework-executed; (2) USAGE.md documents enforced vs non-enforceable boundaries (chat attachments are the unfixable hole — discipline: paths only); (3) dual-mode binary — no args = MCP server, args = standalone CLI; shipped additionally as `maskingtool-windows-standalone.zip`; (4) CLI NER default now follows settings.json (`--enable-ner`/`--no-ner` override); (5) real-web-text test (Wikipedia bio, empty deny-list): NER caught most unlisted names but missed LinkedIn/Seattle Sounders → added via CSV → zero leaks, byte-exact restore (`Test result/M_webtext/`). Upgrade gotcha: kill running `maskingtool-server.exe` (Claude sessions hold the file lock) before rebuilding.

- **2026-07-17** — **Audit capability (feedback: "see what Claude sends to servers")**. Two layers: (Q1) built-in boundary audit log — every MCP tool call appends JSONL to `%APPDATA%\ContentMaskingTool\audit\` recording the exact payload returned to Claude (`src/maskingtool/audit.py`, `tests/test_audit_log.py` 5 passed); deterministic, pinning-proof. Live demo surfaced a real NER miss ("Kwframe Industries" masked in one line, missed in another) — proving the log's value; remedy = deny-list. (Q2) network capture harness `packaging/audit/` (mitmproxy sentinel scanner + per-process-proxy launchers + analyzer); self-test verified the scanner flags leaks and passes clean bodies. User-action remaining: trust mitmproxy CA (system security change — Claude Code must NOT do it), run 3-mode capture (A tool-path=clean / B attachment=leak / C fallback=clean), screenshot. Full procedure in `AUDIT_GUIDE.md`. Suite 130 passed.

- **2026-07-17** — **Mandatory human review shipped (async Review Jobs)**: MCP `mask_document` no longer returns masked text — it opens the GUI detached and returns a `review_id`; content reaches the conversation only via `get_review_result` after the user confirms. New `review.py` store (atomic JSON under `reviews/`, PID-death detection), 5-tool MCP surface, GUI wired (confirm→completed, cancel/close→cancelled, manual terms reported back). Old tests migrated to the new contract incl. the stdio zero-leak test (now: start → out-of-band approve → fetch; sentinels asserted absent across both sessions' streams). **Suite: 140 passed / 0 failed.** Directly answers the reviewer requirement "guaranteed zero-leak needs human review". Remaining: rebuild frozen exe + reinstall extension; first frozen-env test of detached GUI spawn from the extension process.

- **2026-07-20** — **Long-poll review status → MCP auto-continues on Confirm** (user request: clicking "Confirm and create masked file" should hand the masked result to the MCP side automatically, no "I'm done" chat message needed). `get_review_status` now takes `wait_seconds` (default 25, clamped to 55 to stay under MCP client request timeouts); server-side `review.wait_for_decision()` polls the review file every 0.25s and returns the instant the status leaves `waiting_for_user` (Confirm/Cancel/GUI death all unblock it). Tool descriptions + server instructions retargeted: Claude is told to call `get_review_status` immediately after `mask_document` and keep long-polling, then fetch `get_review_result` and continue processing automatically. State machine, GUI, and the mandatory-review guarantee are unchanged. Suite: 146 passed. **Takes effect in the installed extension only after the frozen exe is rebuilt + extension upgraded** (remember the file-lock gotcha: kill running `maskingtool-server.exe` first).

- **2026-07-20** — **Masked outputs centralized in `Documents\Masked Files\`** (user request; supersedes "beside the source" for mask outputs — restore outputs still land beside the masked file). New `config.get_masked_output_dir()`: settings `masked_output_dir` / env `MASKINGTOOL_MASKED_DIR` override, autouse test fixture keeps suite writes out of the real Documents. Suite: 141 passed. Same day: manifest fixed to v1.2.0 with the 5-tool review surface (was stuck at 1.1.0/3 tools, blocking Desktop upgrades), and a **one-click installer** added (`packaging\installer\install.bat`) that installs the Desktop extension (extract + registry record, no UI dependency) and registers a user-scoped Claude Code MCP entry in one run.

- **2026-07-21** — **Release builds made reproducible from a clean checkout.** Added an isolated `.build-venv`, locked `@anthropic-ai/mcpb` 2.1.2 via npm lockfile, cross-platform version/tool metadata validation, full pre-build tests, and SHA-256 release outputs. Replaced slow Windows `Compress-Archive` with `tar.exe` ZIP creation. Synchronized the macOS manifest to the five-tool mandatory-review contract. End-to-end Windows build verified: 148 tests + frozen smoke + MCPB schema validation + checksum verification all passed. GitHub Actions itself remains Stage 2; the build scripts are now runner-ready.

- **2026-07-21** — **Distribution changed to public open source under GNU AGPL-3.0.** This supersedes the 2026-07-14 private/internal distribution decision. PyMuPDF remains bundled under its AGPL option; source history stays free of frozen binaries, local vaults, captures, user configuration, and test evidence. Release binaries belong in GitHub Releases.

## Notes / gotchas discovered

- WindowsApps `python3.exe` on this machine is an install stub — exits with code 49. Don't rely on it.
- `uv python install 3.11` prints a "Missing expected target directory ... minor version link" error on this machine but the interpreter installs and works fine.
- Presidio docs moved: microsoft.github.io/presidio → presidio.dataprivacystack.org.
- Same-value→same-token consistency is NOT automatic in Presidio — the vault's reverse index handles it.
- MCPB manifest spec lives in `modelcontextprotocol/mcpb` — re-check `MANIFEST.md` at packaging time.
- spaCy model for NER mode: `en_core_web_sm` 3.8.0 installed via direct wheel URL (uv).
- Stage 1 known limitations (documented in code): a name split by Markdown inline formatting (`**Acme** Corp`) is not detected; a token split across DOCX runs by later Word edits is not reassembled on restore.
