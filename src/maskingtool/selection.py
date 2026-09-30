"""Map review selections to source using actual substitutions, never a fuzzy diff."""
from dataclasses import dataclass
import difflib

from maskingtool.vault import TOKEN_PATTERN


@dataclass
class Selection:
    text: str
    start: int
    end: int
    masked_originals: list[str]


@dataclass
class DiffRow:
    kind: str
    text: str
    display_start: int
    content_start: int
    content_end: int
    document_start: int


def review_diff(before, after):
    """Legacy red/green rows with offsets excluding decorative +/- prefixes."""
    rows = []
    display_pos = source_pos = output_pos = 0
    source_lines, output_lines = before.splitlines(keepends=True), after.splitlines(keepends=True)
    changes = []
    for opcode, a, b, c, d in difflib.SequenceMatcher(
            None, source_lines, output_lines, autojunk=False).get_opcodes():
        if opcode == "equal":
            changes.extend(("equal", line) for line in source_lines[a:b])
        else:
            changes.extend(("delete", line) for line in source_lines[a:b])
            changes.extend(("insert", line) for line in output_lines[c:d])
    for kind, content in changes:
        prefix = {"delete": "- ", "insert": "+ ", "equal": "  "}[kind]
        # A source without a final newline still needs separate red/green rows.
        text = prefix + content + ("" if content.endswith("\n") else "\n")
        rows.append(DiffRow(kind, text, display_pos, display_pos + 2,
                            display_pos + 2 + len(content),
                            output_pos if kind == "insert" else source_pos))
        display_pos += len(text)
        if kind != "insert":
            source_pos += len(content)
        if kind != "delete":
            output_pos += len(content)
    return rows


def map_diff_selection(before, after, vault, rows, start, end):
    """Project selected diff content back to one exact, contiguous source range.

    Both copies of changed text refer to the same source. Prefixes and display-only
    newlines have no source range and can never become persistent masking rules.
    """
    selections = []
    for row in rows:
        lo, hi = max(start, row.content_start), min(end, row.content_end)
        if lo < hi:
            selections.append(map_selection(
                before, after, vault,
                row.document_start + lo - row.content_start,
                row.document_start + hi - row.content_start,
                masked=row.kind == "insert",
            ))
    if not selections:
        raise ValueError("Select document text, not diff markers.")
    return map_selection(before, after, vault,
                         min(s.start for s in selections), max(s.end for s in selections))


def replacement_ranges(before, after, vault):
    """(output start/end, source start/end, original) for generated tokens."""
    source_pos = output_pos = 0
    ranges = []
    for match in TOKEN_PATTERN.finditer(after):
        unchanged = after[output_pos:match.start()]
        if before[source_pos:source_pos + len(unchanged)] != unchanged:
            raise ValueError("Preview no longer matches its source; reopen the document.")
        source_pos += len(unchanged)
        original = vault.resolve(match.group())
        # Literal tokens already in the input are not a substitution.
        if before.startswith(match.group(), source_pos):
            source_pos += len(match.group())
        elif original is not None and before.startswith(original, source_pos):
            ranges.append((match.start(), match.end(), source_pos, source_pos + len(original), original))
            source_pos += len(original)
        else:
            raise ValueError("Unable to map a preview token back to its source.")
        output_pos = match.end()
    if before[source_pos:] != after[output_pos:]:
        raise ValueError("Preview no longer matches its source; reopen the document.")
    return ranges


def map_selection(before, after, vault, start, end, *, masked=False):
    ranges = replacement_ranges(before, after, vault)
    if not 0 <= start < end <= len(after if masked else before):
        raise ValueError("Select non-empty text in one review panel.")
    if masked:
        def boundary(position, is_end):
            delta = 0
            for out_start, out_end, src_start, src_end, _ in ranges:
                if position <= out_start:
                    return position + delta
                if position < out_end:
                    return src_end if is_end else src_start
                delta = src_end - out_end
            return position + delta
        start, end = boundary(start, False), boundary(end, True)
    originals = list(dict.fromkeys(original for _, _, a, b, original in ranges if start < b and end > a))
    return Selection(before[start:end], start, end, originals)
