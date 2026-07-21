"""Milestone 4 tests: Markdown pipeline — privacy-first full-source masking.

TESTPLAN.md section 4.4 (as amended 2026-07-14: INV-3 wins over code/URL
protection — everything gets masked, structure survives because tokens are
inert text).
"""
from pathlib import Path

import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.parsers.markdown_parser import parse_markdown
from maskingtool.renderers.html_renderer import render_html
from maskingtool.renderers.markdown_renderer import render_masked_markdown
from maskingtool.vault import TOKEN_PATTERN, Vault

FIXTURE = Path(__file__).parent / "fixtures" / "sample.md"

DENY = {
    "ORG": ["Acme Corp", "Bidco Ltd"],
    "PERSON": ["John Smith", "张三"],
}
ALL_TERMS = [t for terms in DENY.values() for t in terms]


@pytest.fixture
def engine():
    return MaskingEngine(deny_lists=DENY, enable_ner=False)


@pytest.fixture
def vault(vaults_dir):
    return Vault.create("sample.md", vaults_dir=vaults_dir)


@pytest.fixture
def source():
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def masked(engine, vault, source):
    spanned = parse_markdown(source)
    new_texts = engine.mask_spanned(spanned, vault)
    return render_masked_markdown(source, spanned, new_texts)


class TestMasking:
    def test_zero_leakage_everywhere(self, masked):
        # INV-3: no deny-list term anywhere — body, code, URLs, front-matter
        for term in ALL_TERMS:
            assert term not in masked, f"leaked: {term}"

    def test_body_text_masked(self, masked):
        assert "# ⟦ORG_" in masked  # heading
        assert "**⟦PERSON_" in masked  # bold

    def test_code_masked_too(self, masked):
        # fenced JSON block and inline code both contain tokens now
        assert '"vendor": "⟦ORG_' in masked
        assert '`owner = "⟦ORG_' in masked

    def test_link_text_and_url_masked(self, masked):
        assert "[⟦ORG_" in masked  # link display text
        # URL-encoded form "Acme%20Corp" is NOT the exact term — documented
        # Stage 1 exact-match semantics; the raw-space URL text does get masked

    def test_front_matter_values_masked(self, masked):
        lines = masked.splitlines()
        assert lines[0] == "---"
        author_line = next(l for l in lines if l.startswith("author:"))
        assert "John Smith" not in author_line
        assert "⟦PERSON_" in author_line


class TestStructure:
    def test_line_count_identical(self, source, masked):
        assert len(masked.splitlines()) == len(source.splitlines())

    def test_markdown_scaffolding_intact(self, masked):
        lines = masked.splitlines()
        assert sum(1 for l in lines if l.strip() == "```json") == 1  # opening fence
        assert sum(1 for l in lines if l.strip() == "```") == 1  # closing fence
        assert any(l.startswith("# ") for l in lines)
        assert any(l.startswith("| ---") for l in lines)

    def test_untouched_line_stays_identical(self, source, masked):
        assert "Closing note without any sensitive names." in masked


class TestRoundTrip:
    def test_exact_round_trip(self, source, masked, vault):
        restored, unresolved = restore_text(masked, vault)
        assert restored == source
        assert unresolved == []

    def test_determinism(self, engine, source, vaults_dir):
        outs = []
        for name in ("a", "b"):
            v = Vault.create(name, vaults_dir=vaults_dir)
            spanned = parse_markdown(source)
            outs.append(
                render_masked_markdown(source, spanned, engine.mask_spanned(spanned, v))
            )
        assert outs[0] == outs[1]


class TestHtmlRender:
    def test_html_contains_tokens_no_leaks(self, masked):
        html = render_html(masked)
        assert TOKEN_PATTERN.search(html)
        for term in ALL_TERMS:
            assert term not in html, f"leaked into HTML: {term}"

    def test_html_has_structure(self, masked):
        html = render_html(masked)
        assert "<h1>" in html
        assert "<table>" in html
        assert "<code" in html
