"""Milestone 6 tests: PDF extraction (read-only) + scanned-page detection.

TESTPLAN.md section 4.6. Fixtures are generated with PyMuPDF at test time
(no binary blobs in the repo).
"""
from pathlib import Path

import pymupdf
import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.parsers.pdf_parser import (
    ScannedPdfError,
    mask_pdf_to_markdown,
    parse_pdf,
)
from maskingtool.vault import TOKEN_PATTERN, Vault

DENY = {
    "ORG": ["Acme Corp", "Bidco Ltd"],
    "PERSON": ["John Smith"],
}
ALL_TERMS = [t for terms in DENY.values() for t in terms]


def _add_scanned_page(doc: pymupdf.Document) -> None:
    """A page containing only a full-page image and no text layer."""
    page = doc.new_page()
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 280), False)
    pix.clear_with(180)  # uniform gray "scan"
    page.insert_image(page.rect, pixmap=pix)


@pytest.fixture
def text_pdf(tmp_path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Quarterly report for Acme Corp.")
    page.insert_text((72, 100), "Prepared by John Smith with Bidco Ltd.")
    page2 = doc.new_page()
    page2.insert_text((72, 72), "Page two mentions Acme Corp again.")
    path = tmp_path / "text.pdf"
    doc.save(str(path))
    return path


@pytest.fixture
def scanned_pdf(tmp_path) -> Path:
    doc = pymupdf.open()
    _add_scanned_page(doc)
    path = tmp_path / "scanned.pdf"
    doc.save(str(path))
    return path


@pytest.fixture
def mixed_pdf(tmp_path) -> Path:
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Text page mentions Acme Corp.")
    _add_scanned_page(doc)
    path = tmp_path / "mixed.pdf"
    doc.save(str(path))
    return path


@pytest.fixture
def engine():
    return MaskingEngine(deny_lists=DENY, enable_ner=False)


@pytest.fixture
def vault(vaults_dir):
    return Vault.create("test.pdf", vaults_dir=vaults_dir)


class TestExtraction:
    def test_names_extracted_with_page_refs(self, text_pdf):
        spanned, warnings = parse_pdf(text_pdf)
        assert "Acme Corp" in spanned.text
        assert "John Smith" in spanned.text
        assert warnings == []
        page_refs = {s.source_ref for s in spanned.spans if s.source_ref}
        assert ("page", 0) in page_refs
        assert ("page", 1) in page_refs


class TestMaskedMarkdown:
    def test_pdf_to_masked_markdown_no_leaks(self, text_pdf, engine, vault):
        masked_md, warnings = mask_pdf_to_markdown(text_pdf, engine, vault)
        for term in ALL_TERMS:
            assert term not in masked_md, f"leaked: {term}"
        assert TOKEN_PATTERN.search(masked_md)
        assert warnings == []

    def test_same_name_same_token_across_pages(self, text_pdf, engine, vault):
        masked_md, _ = mask_pdf_to_markdown(text_pdf, engine, vault)
        assert masked_md.count("⟦ORG_001⟧") == 2  # Acme Corp on page 1 and 2


class TestScannedDetection:
    def test_fully_scanned_pdf_rejected(self, scanned_pdf, engine, vault):
        with pytest.raises(ScannedPdfError) as exc_info:
            mask_pdf_to_markdown(scanned_pdf, engine, vault)
        assert "OCR" in str(exc_info.value)

    def test_mixed_pdf_masks_text_and_warns(self, mixed_pdf, engine, vault):
        masked_md, warnings = mask_pdf_to_markdown(mixed_pdf, engine, vault)
        assert "Acme Corp" not in masked_md
        assert "⟦ORG_001⟧" in masked_md
        assert len(warnings) == 1
        assert "page 2" in warnings[0].lower()
        assert "ocr" in warnings[0].lower()
