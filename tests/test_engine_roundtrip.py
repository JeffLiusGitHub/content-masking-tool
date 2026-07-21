"""Milestone 3 tests: MaskingEngine — mask/restore round-trip on plain strings.

TESTPLAN.md section 4.2. Written before engine.py exists (TDD red phase).
"""
import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.spans import SpannedText, TextSpan
from maskingtool.vault import Vault

DENY = {
    "ORG": ["Acme Corp", "Acme", "Bidco Ltd"],
    "PERSON": ["John Smith", "张三"],
}


@pytest.fixture
def engine():
    return MaskingEngine(deny_lists=DENY, enable_ner=False)


@pytest.fixture
def vault(vaults_dir):
    return Vault.create("test.txt", vaults_dir=vaults_dir)


class TestBasicMasking:
    def test_all_denylist_terms_removed(self, engine, vault):
        masked = engine.mask_text("Acme Corp works with John Smith daily.", vault)
        assert "Acme" not in masked
        assert "John Smith" not in masked
        assert "⟦ORG_001⟧" in masked
        assert "⟦PERSON_001⟧" in masked

    def test_no_match_passthrough(self, engine, vault):
        text = "Nothing sensitive here at all."
        assert engine.mask_text(text, vault) == text
        assert len(vault) == 0

    def test_repeated_mentions_same_token(self, engine, vault):
        masked = engine.mask_text(
            "Acme Corp leads. Acme Corp wins. Acme Corp again.", vault
        )
        assert masked.count("⟦ORG_001⟧") == 3
        assert len(vault) == 1


class TestRoundTrip:
    def test_exact_round_trip(self, engine, vault):
        original = "Acme Corp signed with John Smith and Bidco Ltd.\nLine two: 张三."
        masked = engine.mask_text(original, vault)
        restored, unresolved = restore_text(masked, vault)
        assert restored == original
        assert unresolved == []

    def test_determinism_fresh_vaults(self, engine, vaults_dir):
        text = "Acme Corp, then Bidco Ltd, then John Smith."
        v1 = Vault.create("a.txt", vaults_dir=vaults_dir)
        v2 = Vault.create("b.txt", vaults_dir=vaults_dir)
        assert engine.mask_text(text, v1) == engine.mask_text(text, v2)

    def test_unresolved_token_kept_and_reported(self, engine, vault):
        restored, unresolved = restore_text("Hello ⟦ORG_999⟧ world", vault)
        assert restored == "Hello ⟦ORG_999⟧ world"
        assert unresolved == ["⟦ORG_999⟧"]


class TestMatchingSemantics:
    def test_longest_match_wins(self, engine, vault):
        masked = engine.mask_text("Acme Corp announced results.", vault)
        assert masked == "⟦ORG_001⟧ announced results."
        assert vault.resolve("⟦ORG_001⟧") == "Acme Corp"

    def test_shorter_term_still_matches_alone(self, engine, vault):
        masked = engine.mask_text("Acme announced results.", vault)
        assert masked == "⟦ORG_001⟧ announced results."
        assert vault.resolve("⟦ORG_001⟧") == "Acme"

    def test_word_boundary_no_substring_match(self, vault):
        engine = MaskingEngine(deny_lists={"PERSON": ["Smith"]}, enable_ner=False)
        text = "The Smithsonian is a museum."
        assert engine.mask_text(text, vault) == text

    def test_cjk_name_matches_without_word_boundary(self, engine, vault):
        # CJK text has no spaces; boundary guards must not block the match
        masked = engine.mask_text("今天张三来了公司。", vault)
        assert "张三" not in masked
        assert "⟦PERSON_001⟧" in masked

    def test_punctuation_adjacent(self, engine, vault):
        masked = engine.mask_text("We met Acme Corp. Then (Acme Corp), again.", vault)
        assert "Acme" not in masked
        restored, _ = restore_text(masked, vault)
        assert restored == "We met Acme Corp. Then (Acme Corp), again."

    def test_case_sensitive_exact_match(self, engine, vault):
        # Stage 1 semantics: exact case match only
        text = "acme corp is lowercase."
        assert engine.mask_text(text, vault) == text


class TestSpannedMasking:
    def test_entity_across_span_boundary(self, engine, vault):
        # simulates a DOCX name split across two runs
        spans = [
            TextSpan("Acme ", 0, 5, source_ref="run0"),
            TextSpan("Corp is here", 5, 17, source_ref="run1"),
        ]
        spanned = SpannedText.from_spans(spans)
        new_texts = engine.mask_spanned(spanned, vault)
        assert new_texts == ["⟦ORG_001⟧", " is here"]
        assert vault.resolve("⟦ORG_001⟧") == "Acme Corp"

    def test_spanned_round_trip(self, engine, vault):
        spans = [
            TextSpan("John Smith met ", 0, 15, source_ref=0),
            TextSpan("Acme Corp today", 15, 30, source_ref=1),
        ]
        spanned = SpannedText.from_spans(spans)
        new_texts = engine.mask_spanned(spanned, vault)
        restored, unresolved = restore_text("".join(new_texts), vault)
        assert restored == spanned.text
        assert unresolved == []
