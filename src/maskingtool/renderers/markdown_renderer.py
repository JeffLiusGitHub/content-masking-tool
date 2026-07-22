"""Reassemble masked Markdown source from spans + their masked texts."""
from __future__ import annotations

from maskingtool.operators import apply_replacements
from maskingtool.spans import SpannedText


def render_masked_markdown(
    source: str, spanned: SpannedText, new_texts: list[str]
) -> str:
    replacements = [
        (span.source_ref[0], span.source_ref[1], new_text)
        for span, new_text in zip(spanned.spans, new_texts, strict=False)
        if new_text != span.text
    ]
    return apply_replacements(source, replacements)
