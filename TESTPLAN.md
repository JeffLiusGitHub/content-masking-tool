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
| E2E / release acceptance | Claude Desktop, clean Windows/macOS targets, GitHub Actions | dev-mode flow; frozen exe; `.mcpb`; MSI/PKG lifecycle; signed asset and publication gates | milestones 9–14 |

Coverage target: **≥90% on `vault.py` / `engine.py` / `operators.py` / `recognizers.py`** (the correctness core). Parsers/renderers ≥80%. No coverage chasing on `cli.py` / `server.py` glue.

**NER-dependent tests** are marked `@pytest.mark.ner` and may skip when the
model is unavailable in a development environment. Production builds bundle
the configured spaCy model and enable NER by default; the deterministic
deny-list suite must also remain green when NER is explicitly disabled.

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
| tool discovery | exactly `mask_document`, `get_review_status`, `get_review_result`, `restore_text`, and `restore_document` listed; schemas valid |
| review start is content-free | `mask_document` returns a review handle/status; neither original nor masked document content crosses the MCP boundary before approval |
| review status | `get_review_status` reports `waiting_for_user`, `completed`, `cancelled`, or `failed`; bounded long-polling returns when the state changes |
| review result gate | `get_review_result` returns approved masked content and its `vault_id` only after completion; waiting/cancelled/failed reviews are rejected |
| cross-"session" restore | new server instance (fresh process state) + approved review's `vault_id` → `restore_text` succeeds (INV-5) |
| restore_document docx | full file round-trip via tool calls |
| error: missing file | structured error message, not a traceback |
| error: bad review/vault id | structured not-found error |
| error: unsupported extension | `.xlsx` → clear unsupported-format error |
| error: scanned pdf | surfaced as warning per 4.6 |

## 5. E2E manual checklists (Milestones 9–14)

**M9 — Claude Desktop dev mode:** config points at dev server → tools visible in Claude → "mask report.docx and summarize" works → real names never appear in conversation → next-turn "restore the names" works → restart Claude Desktop mid-flow and restore still works with the old vault_id.

**M10 — Frozen exe (Windows):** `pytest` green first → build → drive frozen exe over stdio with the same MCP client script from 4.8 → all 4.8 cases pass against the binary (catches PyInstaller hidden-import breakage).

**M11 — `.mcpb`:** double-click install on a machine/profile without Python → repeat M9 checklist.

**M12 — macOS:** repeat M10 + M11 on macOS build.

**M13 — managed native installers (planned, not run):** consume the frozen
`onedir` bundles to build a Windows x64 per-machine MSI and separate macOS
arm64/x86_64 PKGs, then run the platform matrices in section 9.

**M14 — atomic signed release (planned, not run):** retain platform MCPBs,
remove standalone ZIPs from formal release assets, and publish only through a
single protected final job after every build/sign/notarize/verify dependency
succeeds.

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

1. Full `pytest` suite green on a clean machine with the locked release
   dependencies installed; any conditional skip is reported and is not counted
   as a pass for a release dependency.
2. `@ner` suite green with the bundled release model present, and deterministic
   deny-list coverage green with NER explicitly disabled.
3. INV-1/INV-3 hold on all three input formats end-to-end via MCP tools.
4. M9–M11 manual checklists signed off on Windows; M12 on macOS.
5. A non-technical user can install the `.mcpb` by double-click and complete mask → summarize → restore in one Claude conversation without touching a terminal.

## 8. Out of scope for this test plan (Stage 2)

Masked PDF/DOCX output rendering, PDF restore, OCR paths, fuzzy/alias matching, ChatGPT/VS Code integrations, performance/load testing (documents are user-scale, not batch-scale).

## 9. Next-release installer and release acceptance

> **Status:** Approved on 2026-09-14. Every case in this section is planned and
> has not been run. It must not be cited as release evidence until a dated
> result identifies the tested commit, package hash, target machine, command,
> result, and log location.

The installer formats begin with the version after v1.2.0. The existing v1.2.0
tag and release remain unchanged. MSI/PKG replace standalone ZIPs as formal
installation assets; Windows and per-architecture macOS MCPBs remain separate
Claude Desktop extension assets. The IDs below are stable acceptance-case
identifiers; their governing release behavior is defined in
[RELEASING.md](RELEASING.md).

### 9.1 Automated metadata and contract tests

| ID | Requirement | Planned acceptance | Status |
|---|---|---|---|
| VER-001 | version normalization | Git tag, application version, three-part MSI ProductVersion, MSI display version, PKG version, MCPB versions, and manifest version agree; prerelease/build metadata, fourth/non-numeric components, leading zeroes, major/minor above 255, and patch above 65535 are rejected without truncation | Partial — source/runtime/MCPB synchronization and native-version rejection tests pass; tag, installed metadata, and final manifest remain pending |
| VER-002 | machine-readable version | both the installed Windows exe and installed macOS launcher print exactly `maskingtool-server MAJOR.MINOR.PATCH`, exit zero, write no other stdout or user data, and do not start GUI or MCP mode | Partial — source and fresh Windows frozen probes pass; installed Windows and both macOS architectures await clean CI evidence |
| META-001 | installer metadata | MSI and PKG metadata expose the expected stable identifiers, version, architecture, and approved publisher/team values | Planned — not run |
| META-002 | release manifest | schema, required fields, asset inventory, size, SHA-256, identifiers, commands, tag, and commit match the built artifacts | Planned — not run |
| META-003 | release notes | extraction selects the matching `CHANGELOG.md` version section and fails when it is missing, empty, or ambiguous | Planned — not run |
| META-004 | implementation language | new installer project names, workflow/job/step identifiers, code comments, and implementation/operator documentation are in English | Implemented — review pending |
| META-005 | local test-build instructions | after installer projects exist, English instructions give reproducible prerequisites, copy-pasteable exact unsigned-test MSI/PKG commands, architecture, output names, and verification steps; before implementation, no fabricated command is published | Implemented — Windows commands locally exercised; macOS commands await native CI |
| SEC-001 | credential isolation | fork and ordinary PR jobs cannot access signing credentials; logs, caches, artifacts, and test snapshots contain no secret material | Planned — not run |
| SEC-002 | protection integrity | no build or test path bypasses production signing, notarization, stapling, Gatekeeper, downgrade protection, or fail-closed publication to obtain a passing result | Planned — not run |

### 9.2 Windows x64 per-machine MSI

Run installation lifecycle cases on a clean Windows runner or VM, including an
MDM-equivalent SYSTEM context where required.

| ID | Planned verification | Acceptance | Status |
|---|---|---|---|
| WIN-001 | package layout | a real WiX 4 per-machine MSI installs the complete PyInstaller onedir tree, including `_internal`, beneath the stable Program Files product directory | Partial — real MSI compiled from complete onedir; elevated installation awaits CI |
| WIN-002 | MSI identity | UpgradeCode remains permanent; ProductCode differs between formal versions but is deterministic across two builds of the same immutable tag; ProductVersion, DisplayVersion, DisplayName, MSI Manufacturer, ARP Publisher, architecture, and registration match their separate release-manifest fields | Planned — not run |
| WIN-003 | silent install | `msiexec /i package.msi /qn /norestart /log install.log` succeeds as SYSTEM using standard MSI exit codes; any possible 3010 handling is documented, no restart is required where avoidable, and version/frozen smoke probes pass afterward | Planned — not run |
| WIN-004 | repeat and upgrade | same-version deployment is idempotent; a prior MSI performs one in-place Major Upgrade; old and new copies do not coexist | Planned — not run |
| WIN-005 | downgrade protection | installing an older package over a newer one is blocked with an intentional, diagnosable result | Planned — not run |
| WIN-006 | managed uninstall | `msiexec /x {ProductCode} /qn /norestart /log uninstall.log` removes only installer-owned program files and registration | Planned — not run |
| WIN-007 | data retention and context | install, repair, upgrade, and ordinary uninstall as SYSTEM preserve user-profile sentinels for `%APPDATA%\ContentMaskingTool\` Vaults, deny lists, settings, history, reviews, and audit data; no application state is redirected into SYSTEM or another user's profile | Planned — not run |
| WIN-008 | signing and hash | applicable EXE/DLL/PYD files are Authenticode-signed before MSI creation; the MSI is then signed with an RFC 3161 timestamp; the Authenticode subject, independently approved ARP Publisher, signatures, version, and SHA-256 verify against their separate manifest fields | Planned — not run |
| WIN-009 | unsigned policy | PR builds may emit clearly labelled unsigned test-only MSI artifacts; a formal tag build fails when production signing is unavailable or invalid | Test path implemented — builder refuses non-test mode; formal signed workflow remains absent/fail-closed |
| WIN-010 | MDM detection | Windows Installer registration by UpgradeCode/ProductCode, the expected installed three-part version, and the installed executable's exact `--version` result agree; detection does not invoke `Win32_Product` | Planned — not run |
| WIN-011 | repair lifecycle | same-version silent repair remains x64/per-machine in SYSTEM context, returns a standard MSI result, restores only installer-owned program files, and preserves all per-user data sentinels | Planned — not run |

### 9.3 macOS PKG, per architecture

Run every applicable case independently for `arm64` and `x86_64`; a universal2
package is out of scope unless every bundled binary is separately proven safe
for that layout.

| ID | Planned verification | Acceptance | Status |
|---|---|---|---|
| MAC-001 | package layout | a real PKG installs the complete onedir payload into the documented machine-level directory and installs only the intended secure launcher/entry point | Planned — not run |
| MAC-002 | architecture | installed Mach-O files match the asset architecture; Intel support is not silently dropped | Planned — not run |
| MAC-003 | silent install | `sudo installer -pkg package.pkg -target /` succeeds non-interactively with expected root ownership and file modes | Planned — not run |
| MAC-004 | receipt and version | `pkgutil --pkg-info` reports the stable package identifier and release version; the application version probe and minimal smoke test pass | Planned — not run |
| MAC-005 | repeat and upgrade | repeated installation is idempotent and a prior PKG upgrades without removing per-user data | Planned — not run |
| MAC-006 | managed uninstall | the PKG installs the root-owned mode-0755 helper at `/Library/Application Support/ContentMaskingTool/uninstall.sh`; the manifest records a literal guarded invocation that is idempotent, removes only allow-listed package files/receipt, and preserves user data | Planned — not run |
| MAC-007 | data retention | install, upgrade, and managed uninstall preserve `~/Library/Application Support/ContentMaskingTool/` | Planned — not run |
| MAC-008 | nested signing | applicable nested Mach-O files are signed from the inside out with Developer ID Application, hardened runtime where applicable, and a secure timestamp | Planned — not run |
| MAC-009 | package trust | the final PKG is signed with Developer ID Installer, submitted with `notarytool`, stapled, and passes `codesign --verify --deep --strict --verbose`, `pkgutil --check-signature`, `spctl -a -vv -t install`, and `xcrun stapler validate` | Planned — not run |
| MAC-010 | unsigned policy | PR builds may emit clearly labelled unsigned layout-test PKGs; a formal tag build fails on missing or failed signing, notarization, stapling, or verification | Test path implemented — builder refuses non-test mode; native CI and formal signed workflow remain pending |
| MAC-011 | uninstall failure safety | empty/root/home/wildcard/parent/unexpected targets are rejected; simulated launcher or payload deletion failure leaves the receipt and retryable helper intact; already-absent fully removed state succeeds; partial state fails | Planned — not run |

### 9.4 Unified release workflow

| ID | Planned verification | Acceptance | Status |
|---|---|---|---|
| REL-001 | source identity | every MSI, PKG, MCPB, checksum, manifest entry, and release note comes from one tag and commit | Planned — not run |
| REL-002 | required assets | final assets include Windows x64 MSI, macOS arm64/x86_64 PKGs, Windows/macOS MCPBs, checksums, and `release-manifest.json` | Planned — not run |
| REL-003 | naming | formal filenames contain product, platform, architecture, and version; standalone ZIP is not uploaded as a formal release asset | Planned — not run |
| REL-004 | atomic publication | platform jobs upload internal artifacts; one protected final job creates a draft only after every required build, test, signature, notarization, and verification succeeds | Planned — not run |
| REL-005 | failure behavior | no `|| true` or equivalent masks release failures, and a failed or missing platform cannot produce a partial public release | Planned — not run |
| REL-006 | release manifest | top-level release identity and each asset's size, hash, signer, installer identifiers, silent-install, uninstall, and version-probe contracts validate | Planned — not run |
| REL-007 | release notes | published notes come from or are synchronized with the matching CHANGELOG section, not only a generated commit comparison | Planned — not run |
| REL-008 | credential boundary | only the protected `release-signing` environment can access signing credentials; temporary certificate, P12, keychain, and API-key material is always deleted | Planned — not run |
| REL-009 | v1.2.0 protection | no workflow step edits, recreates, or uploads replacement assets to the existing v1.2.0 release | Planned — not run |
| REL-010 | MCPB separation | on both platforms, native install, repair/repeat install, upgrade, and uninstall neither install/remove an MCPB nor change pre-existing Claude extension/configuration state | Planned — not run |
| REL-011 | permissions and event guards | only the final release job has `contents: write`; PRs, forks, branches, and unauthorized tags cannot access production credentials, create a draft, or upload any GitHub Release asset | Planned — not run |
| REL-012 | downloaded-asset revalidation | the final job rechecks the downloaded platform artifacts' inventory, byte sizes, SHA-256, versions, installer identifiers, signatures, notarization/staple evidence, tag, and commit before draft publication | Planned — not run |
| REL-013 | forced-failure cleanup | injected build, signing, timestamp, notarization, staple, verification, and upload failures block publication; unconditional cleanup removes temporary PFX/P12/P8/keychain/password material and sanitized logs/artifacts reveal no secrets | Planned — not run |
| MIG-001 | ZIP migration | installers do not scan for or delete arbitrary manually extracted v1.2.0 ZIP copies; any future managed cleanup is restricted to an explicitly approved fixed path | Planned — not run |
| EVD-001 | external environment evidence | when hosted runners cannot reliably cover a system case, a repeatable local/VM script plus English operator instructions exist and record commit, artifact hash, target environment, exact commands, result, and log location; the case remains not run until that evidence exists | Planned — not run |
