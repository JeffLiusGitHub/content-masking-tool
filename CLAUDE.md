# Content Masking Tool — Stage 1 Implementation Plan

> This is the approved Stage 1 plan for this project. Current build status lives in [PROGRESS.md](PROGRESS.md) — read that first to see where work left off.

## Context

Documents sent to Claude (or any AI) often contain confidential company and people names. The goal is a local-first tool that masks those names deterministically before the document/text reaches the AI, and reliably restores the original values afterward — without the user having to learn a new workflow. It should feel like a native part of using Claude: ask Claude to mask a doc, work with the AI on the masked version, then ask Claude to restore it.

Research conclusions:

- **Microsoft Presidio** (MIT) as the detection/anonymization engine — its deny-list `PatternRecognizer` scores matches at 1.0, which naturally outranks any optional NER model (0.4–0.85), giving "deterministic wins" almost for free. Reversibility and same-value→same-token consistency are *not* built in and need a small custom vault-backed operator.
- **MCP + Claude Desktop Extension (.mcpb)** as the delivery mechanism, using `server.type: "binary"` — a PyInstaller-frozen executable per OS — rather than `"python"` (which silently fails on machines without a matching system Python/compiled deps). Release binaries are published separately from Git history as GitHub Release assets.
- A **span-based pipeline**: flatten MD/DOCX/PDF into `TextSpan(text, start, end, source_ref)` objects, run Presidio once over the concatenated text, map offsets back to spans, then re-render per format. This avoids per-format ad hoc string replacement and keeps DOCX formatting intact via run-level (not full-XML) edits.

Target: Windows + macOS, public open-source distribution under AGPL-3.0, Stage 1 scope only (masked MD/HTML output and MD/HTML/DOCX restore; PDF is read/extract-only in Stage 1).

## Active release directive (approved 2026-09-14)

> This directive supersedes the future standalone-ZIP and unsigned-release
> assumptions below. [RELEASING.md](RELEASING.md) is the normative release and
> managed-installation contract, [TESTPLAN.md](TESTPLAN.md) owns acceptance, and
> [PROGRESS.md](PROGRESS.md) records what has actually been implemented and run.

- v1.2.0 remains an immutable historical release: unsigned PyInstaller
  `onedir` standalone ZIPs plus platform MCPBs. Do not alter its tag, release,
  or assets.
- Starting with the next unassigned version, formal standalone distribution is
  a signed x64 per-machine Windows MSI and separate signed, notarized, stapled
  macOS arm64/x86_64 PKGs. The Windows and per-architecture macOS MCPBs remain
  separate required release assets for Claude Desktop.
- Native installers manage machine-level program files only. They must preserve
  each user's Vaults, deny lists, settings, history, reviews, and audit data,
  and they must not search for or delete arbitrary v1.2.0 ZIP extractions.
- PR/local installers may be explicitly unsigned and test-only. A formal tag
  release must fail closed if signing, notarization, stapling, version,
  checksum, installation, or asset verification fails.
- Do not guess the Windows Manufacturer or ARP Publisher, legal signing
  identities, installer identifiers, Apple Team ID, or secret values. Do not
  push, tag, or create/publish a GitHub Release without explicit authorization.

## Windows desktop app — v1.2.0 historical requirements (2026-07-17)

> This section records the v1.2.0 GUI/standalone design. Its ZIP distribution
> rules do not apply to formal releases after v1.2.0; the GUI behavior remains
> relevant. Implementation status and test evidence remain in
> [PROGRESS.md](PROGRESS.md).

### Distribution and three-mode executable

- v1.2.0 shipped the Windows app as
  `dist\maskingtool-windows-standalone.zip`. A user of that historical package
  must retain the entire `maskingtool-server` directory; the executable is not
  standalone from its `_internal` dependencies. Future formal Windows
  standalone distribution uses the MSI contract in
  [RELEASING.md](RELEASING.md).
- The same frozen `maskingtool-server.exe` supports three modes without changing the MCPB manifest:
  1. command-line arguments present → existing CLI;
  2. no arguments and stdin is a pipe → MCP stdio server;
  3. no arguments and no stdin pipe → Windows desktop GUI.
- The GUI hides the console window. CLI stdout/stderr and MCP stdin/stdout must remain unchanged and backwards-compatible.
- Build remains PyInstaller `onedir`, including tkinter/Tcl/Tk, `tkinterdnd2`, Presidio, spaCy, and `en_core_web_sm`.

### Bilingual GUI and onboarding

- All visible GUI content is bilingual: English and Simplified Chinese. This covers the main window, processing states, errors, file dialogs, restore confirmation, Vault selection, history, custom-term list, and tutorial.
- English is the default language. A visible `English / 中文` selector changes the language and persists `gui_language` in `%APPDATA%\ContentMaskingTool\settings.json`.
- On first GUI launch, automatically show a bilingual quick tutorial. Persist `gui_tutorial_seen`; keep a `Tutorial / 使用教程` button so it can always be reopened.
- The tutorial must explain: drop a source file, review without saving, add missed terms, confirm creation, and drop the masked file back to restore.

### Mask preview and explicit approval

- Dropping a normal supported document starts analysis and produces an in-memory preview only. Before approval, do **not** write a masked file, Vault JSON, or history record.
- Show a Git-style read-only diff: removed/original text in red and masked/replacement text in green.
- Present explicit `Confirm and create masked file / 确认并生成脱敏文件` and `Cancel preview / 取消预览` actions.
- Only confirmation commits the masked output, Vault, and history. Cancellation discards the pending preview and creates nothing.
- Masked outputs are written to a central `Documents\Masked Files\` folder (approved 2026-07-20; overridable via `masked_output_dir` in settings.json or `MASKINGTOOL_MASKED_DIR`) and never overwrite an existing file. Use `.masked.md`, followed by numeric suffixes when needed. Restored outputs stay beside the masked file.
- Mask input formats remain `.md`, `.markdown`, `.txt`, `.docx`, and `.pdf`. PDF remains extraction-to-masked-Markdown only; scanned PDFs are rejected or warned as already specified.

### Manual review and persistent missed terms

- In the diff preview, the user can select an exact missed word or phrase and choose `Mask selected text / 遮蔽所选文字`.
- Require classification as `PERSON` or `ORG`. Add the exact, case-sensitive value atomically to the corresponding local user deny-list.
- Re-run masking over the **entire source document**, so every exact occurrence is masked consistently. During an uncommitted preview, recompute the preview without creating files; after an already committed result, create a new non-overwriting revision and reuse its Vault.
- Maintain a separate atomic `manual_terms.json` index for terms added through the GUI. Show only these GUI-added terms in `Custom mask list / 自定义遮蔽列表`; do not mix bundled samples into that view.
- GUI-added terms are permanent local detection rules and must automatically apply to future documents. Duplicate additions must be idempotent.

### Clear restore workflow

- Dropping a known masked output or any supported file containing masking tokens must visibly enter a `Masked file detected / 检测到脱敏文件` state.
- Do not restore silently. Show a dedicated confirmation dialog with explicit `Restore names / 还原姓名` and `Cancel / 取消` buttons.
- Resolve the Vault by exact output-path history first. If the file moved, scan local Vaults and accept only Vaults that resolve every token. If multiple Vaults qualify, require the user to choose; never guess the newest Vault.
- Restore output is written beside the masked file with `.restored` naming and never overwrites an existing file. Unknown tokens remain an error for GUI restore rather than producing a partially restored output.

### Local state, privacy, and sharing

- GUI history is an atomic local index containing input/output paths, action, Vault ID, timestamp, format, and token summary. It has a separate history window and never embeds original secret values.
- Vaults remain local under `%APPDATA%\ContentMaskingTool\vaults\`. They contain sensitive token-to-original mappings and are never bundled into the standalone ZIP or masked output.
- For ordinary collaboration, share only the masked output. Share the corresponding Vault JSON only when the recipient must restore, and only through an approved secure channel.
- For v1.2.0 distribution, share the Windows standalone ZIP, not an isolated
  copy of the executable. Later formal releases use the native installers
  defined in [RELEASING.md](RELEASING.md).

### Windows GUI acceptance criteria

- Source test suite remains green, including: three-mode routing; preview creates no files; commit creates output/Vault/history; cancellation creates nothing; output collision suffixes; unique/ambiguous Vault matching; bilingual defaults and persistence; manual-term idempotency and full-document re-mask; exact round-trip.
- v1.2.0 frozen verification includes MCP stdio smoke, CLI invocation, GUI
  launch, tutorial/language/preview/manual-review/restore checks, and onedir
  ZIP/MCPB artifacts. Future formal releases additionally require the MSI/PKG
  acceptance matrix in [TESTPLAN.md](TESTPLAN.md); source or frozen-binary tests
  are not installer evidence.

## Mandatory human review via async Review Jobs (approved 2026-07-17)

> Supersedes the direct-return `mask_document` contract everywhere on the MCP surface.

- **Every MCP mask request requires human approval in the GUI before any content reaches the conversation.** There is no MCP path that returns masked text without a completed review.
- Async job pattern (never block an MCP call on the user indefinitely): `mask_document(file)` creates a `review_id`, spawns the GUI **detached** (survives MCP server restarts), returns immediately with `waiting_for_user`. `get_review_status(review_id, wait_seconds=25)` **long-polls** (bounded, max 55s per call — under MCP client timeouts) and returns the moment the user clicks Confirm/Cancel, so the model chains straight into `get_review_result(review_id)` without the user having to report back in chat (approved 2026-07-20). `get_review_result` returns the approved `masked_text`, `vault_id`, entity counts, and `manual_terms_added` only after the user confirms.
- State: `%APPDATA%\ContentMaskingTool\reviews\review_<id>.json`, atomic writes, single-direction state machine `waiting_for_user → completed | cancelled | failed`. The GUI records its PID; a status poll that finds the PID dead while still `waiting_for_user` marks the review `failed` ("window closed without a decision").
- GUI side: launched as `<exe> gui --review-id X --file Y`; auto-loads the file into the existing preview flow; Confirm → commit outputs then mark completed (order matters: artifacts before status); Cancel or window close → cancelled. Terms added via `Mask selected text` during the review are reported back in `manual_terms_added`.
- MCP tool surface is now five tools: `mask_document`, `get_review_status`, `get_review_result`, `restore_text`, `restore_document`. Unsupported extensions are rejected up front by `mask_document`.
- CLI `mask` remains direct (the human at the keyboard *is* the reviewer); GUI drag-and-drop keeps its own preview-confirm flow. Tests simulate approval via `MASKINGTOOL_NO_GUI_SPAWN=1` plus `review.complete_review(...)`.

## Dev environment prerequisite

This dev machine only has Python 2.7.18 (`C:\Python27`); the WindowsApps `python3.exe` is an unconfigured Microsoft Store install stub. Presidio/spaCy/MCP require Python 3.11+. Resolution: install `uv` (astral.sh installer) on this machine — it manages its own Python 3.11+ download and the project venv. This is a **dev-machine-only** requirement; end users never install Python, since Stage 1 ships a PyInstaller-frozen binary (`server.type: "binary"` in the MCPB manifest) with everything bundled.

## Repo structure

```
<repo>\
  pyproject.toml
  README.md
  src\maskingtool\
    __init__.py
    __main__.py              # `python -m maskingtool` entry
    cli.py                   # mask / restore subcommands
    config.py                # per-OS app-data path resolution (platformdirs), settings.json
    spans.py                 # TextSpan dataclass + SourceRef types
    vault.py                 # Vault class, on-disk JSON format
    engine.py                # MaskingEngine orchestrator (analyze + anonymize)
    recognizers.py           # deny-list PatternRecognizer builder + registry assembly
    operators.py             # vault-backed anonymize operator + regex-based restore
    parsers\
      markdown_parser.py     # markdown-it-py flatten -> spans (skip code/front-matter/links)
      docx_parser.py         # python-docx flatten -> spans (paragraphs + tables)
      pdf_parser.py          # PyMuPDF text extraction + scanned-page detection (read-only)
    renderers\
      markdown_renderer.py
      html_renderer.py
      docx_renderer.py       # write masked/restored runs back into a .docx copy
    mcp_server\
      server.py              # MCP stdio server entry, tool registration
      tools.py               # five review/mask/restore MCP tool implementations
      schemas.py             # pydantic in/out models
    denylist\
      loader.py              # copies sample lists to app-data on first run, reloads live
    resources\denylist\
      companies.sample.csv
      people.sample.csv
  tests\
    test_vault.py
    test_engine_roundtrip.py
    test_recognizers_priority.py
    test_markdown_pipeline.py
    test_docx_pipeline.py
    test_pdf_extraction.py
    fixtures\ (sample.md, sample.docx, sample.pdf, scanned_page.pdf)
  packaging\
    pyinstaller\
      maskingtool.spec
      build_windows.ps1
      build_macos.sh
    mcpb\
      manifest.json
      icon.png
```

Runs as a normal editable package during development (`uv pip install -e .`, `python -m maskingtool ...`); PyInstaller later freezes the stable entry point `mcp_server/server.py:main`, so internal refactors don't touch the `.spec`.

## Core data model

**`spans.py`** — `TextSpan(text, start, end, source_ref)`. `source_ref` is format-specific: markdown = token index + offset; docx = (paragraph/cell path, run index, char start); pdf = (page, block/span index, bbox) — extraction-only, no write-back in Stage 1. `engine.py` concatenates span texts into one string, runs the Presidio analyzer once, maps each result's offsets back onto overlapping spans.

**`vault.py`** — `Vault.create(source_filename)`, `get_or_create_token(original_value, entity_type)`, `resolve(token)`, `save()`, `Vault.load(vault_id)`. A `reverse_index` (`original_value -> token`) guarantees the same value always maps to the same token. Token format: `⟦{entity_type}_{counter:03d}⟧` (self-describing, regex-extractable). Storage via `platformdirs`:

- Windows: `%APPDATA%\ContentMaskingTool\vaults\vault_<id>.json`
- macOS: `~/Library/Application Support/ContentMaskingTool/vaults/vault_<id>.json`

`vault_id` = timestamp+uuid. Writes are temp-file + `os.replace` for atomicity.

**Operator pair (`operators.py`)** — masking via a Presidio `Operator` subclass (`operator_name="vault_anonymize"`) whose `operate()` calls `vault.get_or_create_token(...)`. **Restore** is a plain regex scan for the token pattern + `vault.resolve()` — deliberately *not* routed through Presidio's `DeanonymizeEngine`, since fixed-format tokens don't need NLP to find, and this keeps restore fast/dependency-light/version-stable.

**Deny-list wiring (`recognizers.py`)** — `build_registry(deny_lists, enable_ner, ner_backend)` starts from an **empty** `RecognizerRegistry()` (no `load_predefined_recognizers()`), adds one `PatternRecognizer(deny_list=terms, deny_list_score=1.0)` per list (ORG, PERSON). When `enable_ner` is true (on by default in the current implementation), it additionally registers a spaCy recognizer at a lower score threshold — it can only add matches Presidio ranks below deny-list hits, never override them. A dedicated test (`test_recognizers_priority.py`) asserts this directly (name present in both deny-list and NER output → deny-list's token wins), not just assumed from default overlap resolution.

NER toggle lives in `%APPDATA%\ContentMaskingTool\settings.json` (`{"enable_ner": true, "ner_backend": "spacy"}`).

## MCP tool shapes

The current MCP surface has five tools and requires out-of-band human review:

1. **`mask_document`** — validates the input, creates a review job, opens the
   local review GUI, and returns `{review_id, status}` without document content.
2. **`get_review_status`** — bounded long-poll for the review state.
3. **`get_review_result`** — returns approved masked text, Vault ID, counts, and
   manual terms only after the review reaches `completed`.
4. **`restore_text`** — restores known tokens in text and reports unresolved
   tokens; state remains on disk across processes.
5. **`restore_document`** — restores a masked file locally and returns the
   output path and unresolved-token result.

`vault_id` is returned by `get_review_result` only after approval and can be
carried across turns — no server-side session state is needed because the
mapping remains on disk even if the frozen binary restarts.

## MCPB packaging plan

The Windows and macOS MCPB manifests use `server.type: "binary"`, point at the
platform frozen binary, and declare the same five review-aware tools. MCPB is a
required release format for Claude Desktop and remains separate from native
standalone installers.

PyInstaller uses `onedir` (not `onefile`), entry =
`mcp_server/server.py:main`, and console mode for MCP stdio. The executable
depends on the adjacent `_internal` tree. Existing scripts and GitHub Actions
build Windows x64 and native macOS arm64/x86_64 frozen bundles and MCPBs. The
future MSI/PKG stages consume those bundles and replace only the formal
standalone ZIP assets; see [RELEASING.md](RELEASING.md).

**Packaging decisions (2026-07-16, requirement change: names are RANDOM, not from a known list):**
- **NER model `en_core_web_sm` is bundled** in the frozen build and `enable_ner` defaults to **true** — random names are detected by NER; the deny-list remains the highest-priority channel for known-critical names.
- **No fixed team name list ships in the package** — bundled sample CSVs are generic placeholders only (Acme Corp / John Smith). Teams add their own names post-install; lists are hot-reloaded per call.
- v1.2.0 builds are unsigned historical artifacts. The 2026-09-14 directive
  supersedes the former decision to defer signing: later formal releases must
  meet the signing and notarization gates in [RELEASING.md](RELEASING.md).

Name lists: bundled sample CSVs ship inside the binary as defaults; `denylist/loader.py` copies them to the app-data dir on first run if absent, and re-reads live on every `mask_document` call (no caching) — editing the CSV takes effect immediately, no rebuild.

## Original Stage 1 build order & verification (historical)

The sequence below records the v1.2.0-era build path. It is not the release
procedure for the planned MSI/PKG pipeline; use [RELEASING.md](RELEASING.md)
and [TESTPLAN.md](TESTPLAN.md) for that work.

1. `spans.py` + `vault.py` + tests — pure data structures, no Presidio. `pytest tests/test_vault.py`.
2. `recognizers.py` + `operators.py` + `engine.py` against plain strings. Verify: masking `"Acme Corp works with John Smith"` produces stable tokens and round-trips exactly through restore.
3. `parsers/markdown_parser.py` + both renderers.
4. `cli.py` + `__main__.py` — first runnable milestone: `python -m maskingtool mask sample.md -o masked.md`, then `restore masked.md --vault-id <id> -o restored.md`.
5. `parsers/docx_parser.py` + `docx_renderer.py`. Verify visually (Word/LibreOffice) that masked runs keep formatting; diff restored text against original.
6. `parsers/pdf_parser.py` (extraction only). Verify a synthetic scanned-page fixture triggers "OCR not supported" instead of silent garbage.
7. `denylist/loader.py` + sample CSVs. Verify editing `companies.csv` in app-data changes the next run's output with zero code changes.
8. `mcp_server/schemas.py` + `tools.py` + `server.py` as thin wrappers over the tested engine. Drive the stdio server directly with the MCP Python SDK's test client — no Claude Desktop yet.
9. Point `claude_desktop_config.json` at the dev-mode server (`python -m maskingtool.mcp_server.server`) to verify the full mask → chat → restore flow in a real Claude conversation, before touching PyInstaller.
10. `maskingtool.spec` + `build_windows.ps1`; verify the frozen `.exe` reproduces step 9 standalone.
11. `manifest.json` + `mcpb pack`; verify by double-click installing the `.mcpb` on Windows.
12. Repeat 10–11 on macOS.

## Stage 1 non-goals

Masked PDF output; PDF restore (PDF is extraction-only); OCR/scanned-page handling (detected and rejected, never attempted); ChatGPT/VS Code integration; auto-update; multi-user/shared vault sync; fuzzy/alias deny-list matching (exact-string match only).

## Critical files

- `src/maskingtool/vault.py`
- `src/maskingtool/engine.py`
- `src/maskingtool/recognizers.py`
- `src/maskingtool/mcp_server/tools.py`
- `packaging/mcpb/manifest.json`
