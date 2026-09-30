"""File-level orchestration shared by the CLI and the MCP tools.

Dispatches on file extension, runs the span pipeline, renders the requested
output format. Formats are added per milestone: markdown (M4), docx (M5),
pdf extraction (M6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
import html
from pathlib import Path

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.renderers.html_renderer import render_html
from maskingtool.textio import read_text_exact, write_text_exact
from maskingtool.vault import Vault

MARKDOWN_SUFFIXES = {".md", ".markdown", ".txt"}
HTML_SUFFIXES = {".html", ".htm"}
MASK_INPUT_SUFFIXES = MARKDOWN_SUFFIXES | HTML_SUFFIXES | {".docx", ".pdf"}


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


def read_document(path: Path) -> tuple[str, list[str]]:
    """Canonical review text, also used verbatim as the engine's input."""
    suffix = path.suffix.lower()
    if suffix in MARKDOWN_SUFFIXES:
        return read_text_exact(path), []
    if suffix in HTML_SUFFIXES:
        from maskingtool.parsers.html_parser import parse_html
        return parse_html(path)
    if suffix == ".docx":
        from maskingtool.parsers.docx_parser import parse_docx, render_markdown_from_docx
        parsed = parse_docx(path)
        return render_markdown_from_docx(parsed, [s.text for s in parsed.spanned.spans]), []
    if suffix == ".pdf":
        from maskingtool.parsers.pdf_parser import parse_pdf
        spanned, warnings = parse_pdf(path)
        pages = [s.text for s in spanned.spans if s.source_ref is not None]
        return "\n\n".join(pages) + "\n", warnings
    raise UnsupportedFormatError(suffix, ", ".join(sorted(MASK_INPUT_SUFFIXES)))


def mask_file(
    path: Path,
    engine: MaskingEngine,
    vault: Vault,
    output_format: str = "markdown",
) -> MaskResult:
    source, warnings = read_document(path)
    masked_md = engine.mask_text(source, vault, html_source=path.suffix.lower() in HTML_SUFFIXES)

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
        source = read_text_exact(path)
        if suffix in HTML_SUFFIXES:
            # Tokens may occur in text or quoted attributes. Escape originals
            # rather than allowing restored names/URLs to become HTML markup.
            from maskingtool.vault import TOKEN_PATTERN
            unresolved = []
            def replace(match):
                original = vault.resolve_html(match.group())
                if original is None:
                    if match.group() not in unresolved:
                        unresolved.append(match.group())
                    return match.group()
                return html.escape(original, quote=True)
            restored = TOKEN_PATTERN.sub(replace, source)
        else:
            restored, unresolved = restore_text(source, vault)
        write_text_exact(output_path, restored)
        return unresolved
    raise UnsupportedFormatError(suffix, ".md, .markdown, .txt, .html, .docx")
