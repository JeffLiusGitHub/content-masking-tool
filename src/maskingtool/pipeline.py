"""File-level orchestration shared by the CLI and the MCP tools.

Dispatches on file extension, runs the span pipeline, renders the requested
output format. Formats are added per milestone: markdown (M4), docx (M5),
pdf extraction (M6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.parsers.markdown_parser import parse_markdown
from maskingtool.renderers.html_renderer import render_html
from maskingtool.renderers.markdown_renderer import render_masked_markdown
from maskingtool.textio import read_text_exact, write_text_exact
from maskingtool.vault import Vault

MARKDOWN_SUFFIXES = {".md", ".markdown", ".txt"}


class UnsupportedFormatError(Exception):
    def __init__(self, suffix: str, supported: str):
        super().__init__(
            f"Unsupported file type '{suffix}'. Supported: {supported}."
        )


@dataclass
class MaskResult:
    masked_text: str
    output_format: str
    warnings: list[str] = field(default_factory=list)


def mask_file(
    path: Path,
    engine: MaskingEngine,
    vault: Vault,
    output_format: str = "markdown",
) -> MaskResult:
    suffix = path.suffix.lower()
    if suffix in MARKDOWN_SUFFIXES:
        source = read_text_exact(path)
        spanned = parse_markdown(source)
        new_texts = engine.mask_spanned(spanned, vault)
        masked_md = render_masked_markdown(source, spanned, new_texts)
        warnings: list[str] = []
    elif suffix == ".docx":
        from maskingtool.parsers.docx_parser import mask_docx_to_markdown

        masked_md, warnings = mask_docx_to_markdown(path, engine, vault)
    elif suffix == ".pdf":
        from maskingtool.parsers.pdf_parser import mask_pdf_to_markdown

        masked_md, warnings = mask_pdf_to_markdown(path, engine, vault)
    else:
        raise UnsupportedFormatError(suffix, ".md, .markdown, .txt, .docx, .pdf")

    if output_format == "html":
        return MaskResult(render_html(masked_md), "html", warnings)
    return MaskResult(masked_md, "markdown", warnings)


def restore_file(
    path: Path, vault: Vault, output_path: Path
) -> list[str]:
    """Restore tokens in a masked file. Returns unresolved tokens."""
    suffix = path.suffix.lower()
    if suffix == ".docx":
        from maskingtool.renderers.docx_renderer import restore_docx

        return restore_docx(path, vault, output_path)
    if suffix in MARKDOWN_SUFFIXES | {".html", ".htm"}:
        restored, unresolved = restore_text(read_text_exact(path), vault)
        write_text_exact(output_path, restored)
        return unresolved
    raise UnsupportedFormatError(suffix, ".md, .markdown, .txt, .html, .docx")
