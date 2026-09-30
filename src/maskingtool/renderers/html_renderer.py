"""Masked Markdown -> HTML."""
from __future__ import annotations

from markdown_it import MarkdownIt
from urllib.parse import quote
import re

_md = MarkdownIt("commonmark").enable("table")


def render_html(masked_markdown: str) -> str:
    rendered = _md.render(masked_markdown)
    # markdown-it percent-encodes Unicode link destinations. Keep vault tokens
    # visible/restorable there, without decoding any other URL or HTML syntax.
    from maskingtool.vault import TOKEN_PATTERN
    for match in TOKEN_PATTERN.finditer(masked_markdown):
        rendered = rendered.replace(quote(match.group(), safe=""), match.group())
    # Only parser-generated line breaks are promoted; arbitrary input HTML
    # remains escaped by markdown-it's default html=False setting.
    return re.sub(r"&lt;br\s*/?&gt;", "<br>", rendered)
