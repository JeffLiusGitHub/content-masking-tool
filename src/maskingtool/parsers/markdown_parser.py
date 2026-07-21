"""Markdown -> spans.

Privacy-first (TESTPLAN 4.4 amendment): the ENTIRE source is maskable —
body, code blocks, inline code, link URLs, front-matter. Tokens are inert
text, so Markdown structure survives masking and restore stays byte-exact.
The whole document is therefore one span; the span model still matters so
Markdown shares the same engine pipeline as DOCX/PDF.

Known Stage 1 limitation: a name interrupted by inline formatting
("**Acme** Corp") is not detected — exact-match semantics only.
"""
from __future__ import annotations

from maskingtool.spans import SpannedText, TextSpan


def parse_markdown(source: str) -> SpannedText:
    span = TextSpan(text=source, start=0, end=len(source), source_ref=(0, len(source)))
    return SpannedText.from_spans([span])
