"""Masked Markdown -> HTML."""
from __future__ import annotations

from markdown_it import MarkdownIt

_md = MarkdownIt("commonmark").enable("table")


def render_html(masked_markdown: str) -> str:
    return _md.render(masked_markdown)
