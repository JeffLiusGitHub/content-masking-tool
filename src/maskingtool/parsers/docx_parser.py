"""DOCX -> spans, masked-docx write-back, and masked-Markdown rendition.

Every run in body paragraphs and table cells becomes one TextSpan whose
source_ref is the live python-docx Run object, so masking writes straight
back into a copy of the document without XML surgery, preserving run-level
formatting (bold/italic/font). A "\n" separator span (source_ref=None) is
inserted between paragraphs/cells so entities can never falsely match
across boundaries — while a name split across runs WITHIN a paragraph is
still detected, because those runs are adjacent in the combined text.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import docx
from docx.document import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from maskingtool.spans import SpannedText, TextSpan
from maskingtool.vault import Vault

# blocks: ("para", style_name, [span_idx...]) | ("table", [[cell_span_indices]])


@dataclass
class DocxParse:
    document: Document
    spanned: SpannedText
    blocks: list


def _iter_block_items(document: Document):
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


class _SpanBuilder:
    def __init__(self):
        self.spans: list[TextSpan] = []
        self._pos = 0

    def add(self, text: str, source_ref) -> int:
        span = TextSpan(text, self._pos, self._pos + len(text), source_ref)
        self._pos += len(text)
        self.spans.append(span)
        return len(self.spans) - 1

    def separator(self):
        self.add("\n", None)


def _paragraph_span_indices(paragraph: Paragraph, builder: _SpanBuilder) -> list[int]:
    indices = []
    for run in paragraph.runs:
        if run.text:
            indices.append(builder.add(run.text, run))
    return indices


def parse_docx(path: Path) -> DocxParse:
    document = docx.Document(str(path))
    builder = _SpanBuilder()
    blocks = []
    for item in _iter_block_items(document):
        if isinstance(item, Paragraph):
            indices = _paragraph_span_indices(item, builder)
            blocks.append(("para", item.style.name if item.style else "", indices))
            builder.separator()
        else:  # Table
            rows = []
            for row in item.rows:
                row_cells = []
                for cell in row.cells:
                    cell_indices = []
                    for p in cell.paragraphs:
                        cell_indices.extend(_paragraph_span_indices(p, builder))
                        builder.separator()
                    row_cells.append(cell_indices)
                rows.append(row_cells)
            blocks.append(("table", rows))
    return DocxParse(document, SpannedText.from_spans(builder.spans), blocks)


def write_masked_docx(parse: DocxParse, new_texts: list[str], output: Path) -> None:
    for span, new_text in zip(parse.spanned.spans, new_texts):
        if span.source_ref is not None and new_text != span.text:
            span.source_ref.text = new_text
    parse.document.save(str(output))


def _heading_prefix(style_name: str) -> str:
    if style_name.startswith("Heading "):
        try:
            level = int(style_name.removeprefix("Heading ").split()[0])
            return "#" * min(level, 6) + " "
        except ValueError:
            pass
    if style_name == "Title":
        return "# "
    return ""


def render_markdown_from_docx(parse: DocxParse, new_texts: list[str]) -> str:
    lines: list[str] = []
    for block in parse.blocks:
        if block[0] == "para":
            _, style_name, indices = block
            text = "".join(new_texts[i] for i in indices)
            lines.append(_heading_prefix(style_name) + text if text else "")
        else:
            _, rows = block
            for row_num, row_cells in enumerate(rows):
                cells = [
                    " ".join(new_texts[i] for i in indices).strip()
                    for indices in row_cells
                ]
                lines.append("| " + " | ".join(cells) + " |")
                if row_num == 0:
                    lines.append("|" + " --- |" * len(cells))
            lines.append("")
    return "\n".join(lines).strip() + "\n"


def mask_docx_to_markdown(path: Path, engine, vault: Vault) -> tuple[str, list[str]]:
    parse = parse_docx(path)
    new_texts = engine.mask_spanned(parse.spanned, vault)
    return render_markdown_from_docx(parse, new_texts), []
