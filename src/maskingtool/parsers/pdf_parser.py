"""PDF -> spans (extraction only in Stage 1 — no masked-PDF output/restore).

Scanned/image-only pages are detected (no extractable text but images
present) and surfaced explicitly: a fully scanned document raises
ScannedPdfError; a mixed document processes its text pages and reports the
scanned ones in warnings. Silent garbage is never produced.
"""
from __future__ import annotations

from pathlib import Path

import pymupdf

from maskingtool.spans import SpannedText, TextSpan
from maskingtool.vault import Vault


class ScannedPdfError(Exception):
    def __init__(self, path: Path):
        super().__init__(
            f"'{path.name}' appears to be a scanned (image-only) PDF. "
            f"OCR is not supported in Stage 1, so its content cannot be "
            f"extracted or masked."
        )


def _is_scanned_page(page: pymupdf.Page) -> bool:
    return not page.get_text().strip() and bool(page.get_images(full=True))


def parse_pdf(path: Path) -> tuple[SpannedText, list[str]]:
    doc = pymupdf.open(str(path))
    try:
        spans: list[TextSpan] = []
        warnings: list[str] = []
        scanned_pages: list[int] = []
        pos = 0

        def _add(text: str, ref) -> None:
            nonlocal pos
            spans.append(TextSpan(text, pos, pos + len(text), ref))
            pos += len(text)

        for page_num, page in enumerate(doc):
            text = page.get_text().strip()
            if text:
                _add(text, ("page", page_num))
                _add("\n", None)  # boundary: no cross-page false matches
            elif _is_scanned_page(page):
                scanned_pages.append(page_num)

        if scanned_pages and not spans:
            raise ScannedPdfError(path)
        for page_num in scanned_pages:
            warnings.append(
                f"Page {page_num + 1} appears to be scanned (image-only); OCR is "
                f"not supported in Stage 1, so its content was NOT extracted or "
                f"masked."
            )
        return SpannedText.from_spans(spans), warnings
    finally:
        doc.close()


def mask_pdf_to_markdown(path: Path, engine, vault: Vault) -> tuple[str, list[str]]:
    spanned, warnings = parse_pdf(path)
    new_texts = engine.mask_spanned(spanned, vault)
    pages = [
        text
        for span, text in zip(spanned.spans, new_texts)
        if span.source_ref is not None
    ]
    return "\n\n".join(pages) + "\n", warnings
