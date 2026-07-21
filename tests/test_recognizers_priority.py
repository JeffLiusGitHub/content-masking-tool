"""Milestone 3 tests: deny-list priority over NER; registry cleanliness.

TESTPLAN.md section 4.3.
"""
import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.vault import Vault

from conftest import requires_ner


@pytest.fixture
def vault(vaults_dir):
    return Vault.create("test.txt", vaults_dir=vaults_dir)


class TestDenyListOnly:
    def test_denylist_results_score_one(self):
        engine = MaskingEngine(deny_lists={"ORG": ["Acme Corp"]}, enable_ner=False)
        results = engine.analyze("We visited Acme Corp today.")
        assert len(results) == 1
        assert results[0].score == 1.0
        assert results[0].entity_type == "ORG"

    def test_ner_off_means_ner_silent(self, vault):
        # a famous person NOT in the deny-list must be untouched when NER is off
        engine = MaskingEngine(deny_lists={"ORG": ["Acme Corp"]}, enable_ner=False)
        text = "Barack Obama emailed obama@example.com from Washington."
        assert engine.mask_text(text, vault) == text

    def test_no_predefined_recognizers_leak(self, vault):
        # emails/phones/credit cards: Presidio predefined recognizers must NOT run
        engine = MaskingEngine(deny_lists={"ORG": ["Acme Corp"]}, enable_ner=False)
        text = "Call 555-0100 or mail jane@example.com, card 4111111111111111."
        assert engine.mask_text(text, vault) == text


@requires_ner
class TestNerIntegration:
    def test_denylist_beats_ner(self, vault):
        # "John Smith" is deliberately listed as ORG; spaCy NER would say PERSON.
        # The deny-list entity type must win for that span.
        engine = MaskingEngine(deny_lists={"ORG": ["John Smith"]}, enable_ner=True)
        masked = engine.mask_text("John Smith attended the meeting.", vault)
        assert "⟦ORG_001⟧" in masked
        assert "PERSON" not in masked

    def test_ner_adds_but_never_overrides(self, vault):
        engine = MaskingEngine(
            deny_lists={"ORG": ["Acme Corp"]}, enable_ner=True
        )
        masked = engine.mask_text(
            "Barack Obama visited Acme Corp in Washington.", vault
        )
        # deny-list hit still resolves to its own token
        assert vault.resolve("⟦ORG_001⟧") == "Acme Corp"
        # NER catches the person not in any list
        assert "Barack Obama" not in masked

    def test_ner_results_below_denylist_score(self):
        engine = MaskingEngine(deny_lists={"ORG": ["Acme Corp"]}, enable_ner=True)
        results = engine.analyze("Barack Obama visited Acme Corp.")
        by_text = {}
        for r in results:
            by_text[(r.start, r.end)] = r
        denylist_scores = [r.score for r in results if r.entity_type == "ORG"]
        ner_scores = [r.score for r in results if r.entity_type != "ORG"]
        assert all(s == 1.0 for s in denylist_scores)
        assert all(s < 1.0 for s in ner_scores)
