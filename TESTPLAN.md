# Test Plan & TDD Workflow — Content Masking Tool (Stage 1)

> Companion to [CLAUDE.md](CLAUDE.md) (plan) and [PROGRESS.md](PROGRESS.md) (status).
> Rule of thumb: **no production module is written before its failing tests exist.**

## 1. Why TDD fits this project

The core promise of this tool is *lossless reversibility*: `restore(mask(text)) == text`, byte-for-byte, every time, including across process restarts. That property is cheap to assert in a test and catastrophic to get silently wrong in production (a leaked real name, or a corrupted restored document). So the test suite is not an afterthought — it IS the specification of correctness.

**Red → Green → Refactor loop per milestone:**

1. Write the test file for the milestone first (tests fail — red).
2. Implement the minimal module code to pass (green).
3. Refactor freely — the round-trip invariants keep you honest.
4. Only then move to the next milestone. Never build milestone N+1 on untested milestone N.

## 2. Test pyramid

| Layer | Tooling | Scope | Run frequency |
|---|---|---|---|
| Unit | pytest | vault, spans, recognizers, operators, each parser/renderer in isolation | every change (`pytest -x`) |
| Integration | pytest | full engine pipeline per format; MCP server driven by MCP SDK in-memory client | every milestone completion |
| E2E (manual checklist) | Claude Desktop | dev-mode config flow; frozen exe; `.mcpb` double-click install | milestones 9–12 |

Coverage target: **≥90% on `vault.py` / `engine.py` / `operators.py` / `recognizers.py`** (the correctness core). Parsers/renderers ≥80%. No coverage chasing on `cli.py` / `server.py` glue.

**NER-dependent tests** are marked `@pytest.mark.ner` and auto-skip when the spaCy/GLiNER model isn't downloaded — the default suite must pass on a fresh offline machine, because deny-list-only is the default product configuration.

## 3. Universal invariants (property-style, asserted everywhere applicable)

- **INV-1 Round-trip**: for any input text and any deny-list, `restore(mask(text)) == text` exactly.
- **INV-2 Consistency**: the same original value yields the same token at every occurrence, within a document and across `mask` calls reusing the same vault.
- **INV-3 No leakage**: masked output contains **zero** occurrences of any deny-list term (case-sensitive exact match, Stage 1 semantics).
- **INV-4 Determinism**: masking the same document twice with a fresh vault yields identical output (token numbering is order-of-appearance, not random).
- **INV-5 Persistence**: a vault saved, process "restarted" (new object, load from disk), then used to restore, behaves identically to the in-memory vault.

## 4. Per-module test specifications

### 4.1 `tests/test_vault.py` (Milestone 2)

| Case | Assertion |
|---|---|
| token format | first PERSON token is `⟦PERSON_001⟧`; ORG counter independent of PERSON counter |
| same value → same token | two `get_or_create_token("Acme Corp", "ORG")` calls return identical token (INV-2) |
| distinct values increment | "Acme" then "Bidco" → `_001`, `_002` |
| resolve round-trip | `resolve(token)` returns the exact original, including unicode (中文姓名, accented chars) |
| resolve unknown | unknown/malformed token → `None`, no exception |
| save/load round-trip | save → `Vault.load(vault_id)` → all mappings + counters + reverse_index intact (INV-5) |
| atomic write | after `save()`, file parses as valid JSON; a second save doesn't corrupt on simulated interrupt (write to temp + `os.replace`) |
| load missing id | clear `VaultNotFoundError` (or equivalent), not a raw `FileNotFoundError` traceback |
| storage isolation | tests use `tmp_path`-overridden app-data dir — never touch the real `%APPDATA%` |

### 4.2 `tests/test_engine_roundtrip.py` (Milestone 3)

| Case | Assertion |
|---|---|
| basic mask | `"Acme Corp works with John Smith"` + deny-list → both replaced by typed tokens; no deny-list term remains (INV-3) |
| exact round-trip | restore of masked text == original, byte-for-byte (INV-1) |
| repeated mentions | name appearing 3× → same token 3× (INV-2) |
| longest-match wins | deny-list has both "Acme" and "Acme Corp"; text "Acme Corp" → single `⟦ORG_nnn⟧`, not a nested/partial mess |
| no-match passthrough | text with no deny-list hits → returned unchanged, vault has zero entries |
| determinism | two fresh-vault runs on same input → identical masked output (INV-4) |
| unresolved token | restoring text containing `⟦ORG_999⟧` not in vault → token left intact + listed in `unresolved_tokens` |
| word-boundary safety | deny-list "Smith" must not fire inside "Smithsonian" (document actual chosen semantics with a test either way) |
| multi-word + punctuation | "Acme Corp." / "Acme Corp," at sentence end handled correctly |

### 4.3 `tests/test_recognizers_priority.py` (Milestone 3)

| Case | Assertion |
|---|---|
| clean registry | built registry contains **only** the deny-list recognizers when NER off — no predefined Presidio recognizers |
| score | deny-list results carry score 1.0 |
| NER off = NER silent | with `enable_ner=False`, a famous name NOT in the deny-list is untouched |
| deny-list beats NER `@ner` | name present in deny-list as ORG while NER would tag PERSON → final result is the deny-list's ORG token |
| NER adds, never overrides `@ner` | NER-only names get masked at lower score; every deny-list span still resolves to the deny-list token |

### 4.4 `tests/test_markdown_pipeline.py` (Milestone 3–4)

> **Decision (2026-07-14):** an earlier draft of this section protected code blocks
> and link URLs from masking. That contradicts INV-3 (zero leakage) — a company name
> inside a code block would reach the AI unmasked. INV-3 wins: **everything is masked**,
> including code, URLs, and front-matter values. Tokens are inert text, so Markdown
> structure survives and round-trip stays exact. Trade-off: links containing a masked
> name are broken while masked; restore brings them back.

Fixture: `tests/fixtures/sample.md` — deliberately contains front-matter, headings, bold/italic, a fenced code block and inline code *containing a deny-list name*, a link whose **text** and whose **URL** both contain a deny-list name, a table, and a list.

| Case | Assertion |
|---|---|
| body text masked | names in paragraphs/headings/lists/tables replaced |
| code masked too | name inside fenced block and inline code replaced (INV-3, privacy-first) |
| link handling | both link display text and `href` URL masked when they contain a deny-list name |
| front-matter masked | names in YAML values replaced; YAML keys/structure intact |
| structure preserved | masked output has identical line count; headings/fences/table pipes intact; only name substrings differ |
| round-trip | mask → restore == original file content exactly (INV-1) |
| HTML render | masked MD → HTML contains tokens, zero deny-list terms anywhere (INV-3) |
| known limitation | a name split by inline formatting (`**Acme** Corp`) is NOT detected in Stage 1 — documented, not asserted |

### 4.5 `tests/test_docx_pipeline.py` (Milestone 5)

Fixture: `tests/fixtures/sample.docx` built **programmatically in a fixture function** (not a binary blob in git) — paragraphs with bold/italic runs, a name deliberately **split across two runs** ("Acme " + "Corp"), and a 2×2 table containing names.

| Case | Assertion |
|---|---|
| span extraction | paragraph + table cell text fully captured with run offsets |
| split-run detection | the run-split "Acme Corp" is still detected and masked as one entity |
| formatting preserved | masked docx: first overlapping run keeps bold/italic; doc opens cleanly via python-docx re-read |
| table masking | names inside table cells masked |
| restore into docx | restore_document on the masked copy → full text content == original document text |
| masked-doc leak check | concatenated text of masked docx contains zero deny-list terms (INV-3) |

### 4.6 `tests/test_pdf_extraction.py` (Milestone 6)

Fixtures: `sample.pdf` (text-based, generated via PyMuPDF in a fixture) and `scanned_page.pdf` (a page containing only a full-page image).

| Case | Assertion |
|---|---|
| text extraction | names extracted into spans with page refs |
| pipeline to MD | PDF in → masked Markdown out, tokens present, no deny-list terms (INV-3) |
| scanned detection | scanned fixture → explicit "OCR not supported in Stage 1" warning/error, **not** empty/garbage output |
| mixed doc | text page + scanned page → text page processed, scanned page flagged in `warnings` |

### 4.7 Deny-list loader tests (Milestone 7, in `test_recognizers_priority.py` or own file)

| Case | Assertion |
|---|---|
| first-run copy | samples copied to (tmp) app-data dir when absent; NOT overwritten when present |
| live reload | edit CSV between two engine runs → second run masks the newly added name, no restart |
| encoding | UTF-8 with BOM and Chinese entries load correctly |
| malformed rows | blank/comment lines skipped without crashing; warning surfaced |

### 4.8 MCP server integration tests (Milestone 8) — `tests/test_mcp_server.py`

Driven via the MCP Python SDK in-memory/stdio test client. No Claude Desktop involved.

| Case | Assertion |
|---|---|
| tool discovery | exactly `mask_document`, `restore_text`, `restore_document` listed, schemas valid |
| mask happy path | mask fixture `.md` → response has `vault_id`, `masked_text`, `entity_counts`; masked_text clean (INV-3) |
| cross-"session" restore | new server instance (fresh process state) + old `vault_id` → `restore_text` succeeds (INV-5) |
| restore_document docx | full file round-trip via tool calls |
| error: missing file | structured error message, not a traceback |
| error: bad vault_id | structured "vault not found" error |
| error: unsupported extension | `.xlsx` → clear unsupported-format error |
| error: scanned pdf | surfaced as warning per 4.6 |

## 5. E2E manual checklists (Milestones 9–12)

**M9 — Claude Desktop dev mode:** config points at dev server → tools visible in Claude → "mask report.docx and summarize" works → real names never appear in conversation → next-turn "restore the names" works → restart Claude Desktop mid-flow and restore still works with the old vault_id.

**M10 — Frozen exe (Windows):** `pytest` green first → build → drive frozen exe over stdio with the same MCP client script from 4.8 → all 4.8 cases pass against the binary (catches PyInstaller hidden-import breakage).

**M11 — `.mcpb`:** double-click install on a machine/profile without Python → repeat M9 checklist.

**M12 — macOS:** repeat M10 + M11 on macOS build.

## 6. Fixtures inventory

| File | Purpose | How created |
|---|---|---|
| `fixtures/sample.md` | markdown feature coverage (4.4) | hand-written, checked in |
| `fixtures/sample.docx` | run-splits, formatting, tables (4.5) | generated by fixture code at test time |
| `fixtures/sample.pdf` | text PDF (4.6) | generated by fixture code (PyMuPDF) |
| `fixtures/scanned_page.pdf` | scanned-page detection (4.6) | generated: full-page image, no text layer |
| `fixtures/denylist_test.csv` | loader tests (4.7) | hand-written, includes 中文 + BOM cases |

Generated fixtures keep binary blobs out of the repo and make the fixture's structure readable in code.

## 7. Stage 1 acceptance criteria (definition of done)

1. Full `pytest` suite green on a clean machine **without** any NER model downloaded (deny-list-only default).
2. `@ner` suite green on a machine with the model present.
3. INV-1/INV-3 hold on all three input formats end-to-end via MCP tools.
4. M9–M11 manual checklists signed off on Windows; M12 on macOS.
5. A non-technical user can install the `.mcpb` by double-click and complete mask → summarize → restore in one Claude conversation without touching a terminal.

## 8. Out of scope for this test plan (Stage 2)

Masked PDF/DOCX output rendering, PDF restore, OCR paths, fuzzy/alias matching, ChatGPT/VS Code integrations, performance/load testing (documents are user-scale, not batch-scale).
