# HTML and editable review rules (v1.3.0-rc.1)

These capabilities are included in the unsigned v1.3.0-rc.1 testing prerelease. They
are **not** a replacement publication of the v1.2.0 release.

## Input and output

The GUI, CLI and five-tool MCP server accept `.html` and `.htm` in addition to
Markdown, text, DOCX and PDF. HTML is parsed locally without running scripts or
requesting images, stylesheets, links or other remote resources. Titles,
paragraphs, lists, image alternative text, link labels/targets and tables are
converted into the same canonical Markdown shown in the review preview.

Table row/column relationships are retained. Merged cells repeat their content
over the covered cells; nested tables become lines inside the parent cell and
produce a warning. Styles, scripts, comments and non-output attributes are
discarded. This is semantic conversion, not a browser renderer or a byte-exact
HTML editor. Restoring Markdown returns the canonical Markdown; restoring HTML
returns safe simplified HTML with the original values. Original page code and
styling cannot be reconstructed. Excel files remain unsupported.

## URL and multiline masking

HTTP, HTTPS and `www.` addresses are detected offline even when NER is off.
Paths, parameters and fragments are included. Bare domains are not automatically
classified as URLs. Actual line breaks are never joined speculatively: select
the entire broken address manually and choose **URL**.

Manual categories are Person, Organization, URL and Text, producing
`⟦PERSON_001⟧`, `⟦ORG_001⟧`, `⟦URL_001⟧` and `⟦TEXT_001⟧` respectively.
Each multiline selection becomes one token. Internal/leading/trailing spaces,
LF and CRLF are preserved; whitespace-only selections are rejected. Exact
matching does not normalize different newline or whitespace arrangements.

The original single red/green diff layout is restored: red minus rows show
original text, green plus rows show replacements below, and unchanged rows
appear once. Select text in this preview, including across multiple lines.
Diff prefixes and display-only newlines are excluded from selections; selecting
both copies of changed content refers to one contiguous original range.
A result selection containing a token is mapped
back to its original text, including when it is only part of a longer URL.
Clicking a generated token selects it in full with a blue background. Drag or
keyboard selections touching part of a token visibly expand to its boundaries;
multiple tokens can be selected together. The highlight remains when focus moves
to the action button. Clicking ordinary text clears the selection. This does
not change any rules until **Unmask selected** (or **Mask selected text**) is
clicked. Literal token-shaped text is not treated as a generated token.
Partially selected tokens expand to the whole original value.

## Unmasking and persistent lists

Select an existing masked item (or its original text), then click **Unmask
selected**. Selecting text alone does not change rules. A selection containing
multiple masked items unmarks each independently, at every identical occurrence.

* A direct deny-list entry is removed from CSV/manual records and allowed for
  the current review only. It is **not** automatically added to the permanent
  allow list. NER/URL recognition may mask it again in a future review.
* An automatic detection or derived name part is added to the permanent allow
  list. Removing a name part never deletes the parent full-name entry.
* Manually masking an allowed value removes its exact allow/session exception
  and adds the selected category to the deny list again.

Priority: explicit allow/session ranges, manual selections, automatic URLs,
deny-list detections, then NER. An allowed substring protects only its own exact
range: the rest of a longer URL remains maskable. Name matching keeps existing
case-sensitive and word-boundary behavior. NER false positives remain possible;
unmasking provides correction rather than changing the model.

**Rule edits are immediately persistent and survive Cancel preview.** Cancelling
does not publish an output or an MCP review result. Existing outputs are never
overwritten; editing after confirmation creates a new preview that requires a
new confirmation. Existing Vault mappings are retained and token numbers are
not renumbered; displayed counts include only tokens used in the current output.

The **Deny / allow lists** window shows rule categories and source files and
supports deletion. Deletion there removes the rule without adding the other
kind of rule. The next preview reflects the remaining detection rules.

## Storage and compatibility

All lists are in the existing per-user `denylists` directory. `people.csv` and
`companies.csv` remain live-editable. `manual_terms.json` is now an active rule
source, including URL/Text and multiline values; removing a duplicated manual
rule requires removing its CSV and JSON entries (the GUI does both).
`allow_terms.json` contains `{"terms": ["exact value", "another value"]}`.
Missing allow files mean no exceptions; malformed files stop analysis with an
error. Concurrent app edits are file-locked. Failed writes or preview generation
roll back the complete rule operation and retain the prior preview.

Old Vaults and tokens need no migration. New HTML-created mappings may contain
an optional `html_original` field for safe semantic restoration of escaped text.
The five MCP tools and the human-approval gate are unchanged; rule management
is local UI functionality, not a new AI-callable tool.

## Verification

Regression coverage lives in `test_html_input.py`, `test_review_enhancements.py`
and `test_review_gui.py`, plus the existing complete suite. Tk tests use a real
hidden root; Linux requires a display/Xvfb. The frozen smoke command is:

```powershell
.venv\Scripts\python.exe packaging\pyinstaller\smoke_review_features.py <test-executable>
```

Use synthetic fixtures and isolated app data when testing. The original IE
discovery schedule, managed IE Windows laptop and macOS artifacts need separate
acceptance; local source tests do not establish those results.
