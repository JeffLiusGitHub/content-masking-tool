# Content Masking Tool — Stage 1 Implementation Plan

> This is the approved Stage 1 plan for this project. Current build status lives in [PROGRESS.md](PROGRESS.md) — read that first to see where work left off.

## Context

Documents sent to Codex (or any AI) often contain confidential company and people names. The goal is a local-first tool that masks those names deterministically before the document/text reaches the AI, and reliably restores the original values afterward — without the user having to learn a new workflow. It should feel like a native part of using Codex: ask Codex to mask a doc, work with the AI on the masked version, then ask Codex to restore it.

Research conclusions:

- **Microsoft Presidio** (MIT) as the detection/anonymization engine — its deny-list `PatternRecognizer` scores matches at 1.0, which naturally outranks any optional NER model (0.4–0.85), giving "deterministic wins" almost for free. Reversibility and same-value→same-token consistency are *not* built in and need a small custom vault-backed operator.
- **MCP + Claude Desktop Extension (.mcpb)** as the delivery mechanism, using `server.type: "binary"` — a PyInstaller-frozen executable per OS — rather than `"python"` (which silently fails on machines without a matching system Python/compiled deps). Release binaries are published separately from Git history as GitHub Release assets.
- A **span-based pipeline**: flatten MD/DOCX/PDF into `TextSpan(text, start, end, source_ref)` objects, run Presidio once over the concatenated text, map offsets back to spans, then re-render per format. This avoids per-format ad hoc string replacement and keeps DOCX formatting intact via run-level (not full-XML) edits.

Target: Windows + macOS, public open-source distribution under AGPL-3.0, Stage 1 scope only (masked MD/HTML output and MD/HTML/DOCX restore; PDF is read/extract-only in Stage 1).

## Active release directive (approved 2026-09-14)

> This directive supersedes the standalone-ZIP, unsigned-release, `onefile`,
> three-tool, and no-CI assumptions elsewhere in this historical Stage 1 plan.
> Current implementation evidence belongs in [PROGRESS.md](PROGRESS.md), the
> normative packaging contract belongs in [RELEASING.md](RELEASING.md), and
> release acceptance belongs in [TESTPLAN.md](TESTPLAN.md).

- The tagged v1.2.0 release remains an unsigned PyInstaller `onedir` ZIP plus
  platform-specific MCPB assets. Do not alter or republish its tag or release.
- Beginning with the next, as-yet-unassigned release, the formal standalone
  assets must be a signed x64 per-machine Windows MSI and separate signed,
  notarized, and stapled macOS arm64/x86_64 PKGs. MCPB remains a separate,
  required Claude Desktop extension asset and is not replaced by MSI/PKG.
- Standalone ZIPs may remain test/debug workflow artifacts, but must not be
  attached to a formal release after v1.2.0. Native installers do not silently
  install or register the MCPB extension.
- Formal tag builds fail closed if signing, notarization, stapling, metadata,
  checksum, installation, or release-asset verification fails. PR/local builds
  may emit only clearly labelled unsigned, test-only installers.
- MSI/PKG upgrades and normal uninstalls must preserve per-user Vaults, deny
  lists, settings, history, reviews, and audit data. Legacy ZIP copies in
  arbitrary locations must not be scanned for or deleted.
- Never invent a Windows Manufacturer or ARP Publisher, certificate identity,
  UpgradeCode, Apple Team ID, package identifier, or secret value. These are
  release-blocking inputs until the owner confirms them.
- Do not push, create a tag, or create/publish a GitHub Release without explicit
  authorization.

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
2. **`get_review_status`** — bounded long-poll for `waiting_for_user`,
   `completed`, `cancelled`, or `failed`.
3. **`get_review_result`** — returns approved masked text, Vault ID, counts, and
   manual terms only after the review reaches `completed`.
4. **`restore_text`** — loads a Vault, regex-scans tokens, resolves known values,
   and reports unresolved tokens.
5. **`restore_document`** — restores a masked file locally and returns its
   output path and unresolved-token result.

`vault_id` is returned by `get_review_result` only after approval and can be
carried across turns — no server-side session state is needed because the
mapping remains on disk even if the frozen binary restarts.

## MCPB packaging plan

The Windows and macOS MCPB manifests use `server.type: "binary"`, point at the
platform frozen binary, and declare the same five review-aware tools. MCPB is a
required release format for Claude Desktop and remains separate from native
standalone installers.

PyInstaller currently uses `onedir` (not `onefile`), entry =
`mcp_server/server.py:main`; the executable depends on the adjacent `_internal`
tree. Existing scripts and GitHub Actions build Windows x64 and native macOS
arm64/x86_64 frozen bundles, MCPBs, ZIPs, and checksums. For formal releases
after v1.2.0, WiX 4 MSI and signed/notarized PKG stages must consume those
onedir bundles and replace only the formal standalone ZIP assets. See
[RELEASING.md](RELEASING.md) for the complete contract.

Name lists: bundled sample CSVs ship inside the binary as defaults; `denylist/loader.py` copies them to the app-data dir on first run if absent, and re-reads live on every `mask_document` call (no caching) — editing the CSV takes effect immediately, no rebuild.

## Original Stage 1 build order & verification (historical)

The sequence below records how the v1.2.0-era product was built. It is not the
release procedure for the planned MSI/PKG pipeline; use
[RELEASING.md](RELEASING.md) and [TESTPLAN.md](TESTPLAN.md) for that work.

1. `spans.py` + `vault.py` + tests — pure data structures, no Presidio. `pytest tests/test_vault.py`.
2. `recognizers.py` + `operators.py` + `engine.py` against plain strings. Verify: masking `"Acme Corp works with John Smith"` produces stable tokens and round-trips exactly through restore.
3. `parsers/markdown_parser.py` + both renderers.
4. `cli.py` + `__main__.py` — first runnable milestone: `python -m maskingtool mask sample.md -o masked.md`, then `restore masked.md --vault-id <id> -o restored.md`.
5. `parsers/docx_parser.py` + `docx_renderer.py`. Verify visually (Word/LibreOffice) that masked runs keep formatting; diff restored text against original.
6. `parsers/pdf_parser.py` (extraction only). Verify a synthetic scanned-page fixture triggers "OCR not supported" instead of silent garbage.
7. `denylist/loader.py` + sample CSVs. Verify editing `companies.csv` in app-data changes the next run's output with zero code changes.
8. `mcp_server/schemas.py` + `tools.py` + `server.py` as thin wrappers over the tested engine. Drive the stdio server directly with the MCP Python SDK's test client — no Codex Desktop yet.
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
