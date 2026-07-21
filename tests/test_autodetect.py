"""GUI core logic (headless-testable): action auto-detection and automatic
vault matching for dropped files. The tkinter shell itself is a thin layer
over these + the existing pipeline.
"""
import pytest

from maskingtool.autodetect import detect_action, find_vault_for_text
from maskingtool.engine import MaskingEngine
from maskingtool.vault import Vault

DENY = {"PERSON": ["Zebulon Quarkfield"], "ORG": ["Vortexia Dynamics"]}


@pytest.fixture
def engine():
    return MaskingEngine(deny_lists=DENY, enable_ner=False)


class TestDetectAction:
    def test_plain_text_means_mask(self):
        assert detect_action("Zebulon Quarkfield met the board.") == "mask"

    def test_tokens_mean_restore(self):
        assert detect_action("⟦PERSON_001⟧ met the board.") == "restore"

    def test_mixed_content_means_restore(self):
        # partially masked file: restoring is the only safe interpretation
        assert detect_action("⟦PERSON_001⟧ met Zebulon Quarkfield.") == "restore"


class TestFindVault:
    def test_finds_matching_vault(self, engine, vaults_dir):
        v = Vault.create("a.md", vaults_dir=vaults_dir)
        masked = engine.mask_text("Zebulon Quarkfield of Vortexia Dynamics.", v)
        v.save()

        found = find_vault_for_text(masked, vaults_dir=vaults_dir)
        assert found is not None
        assert found.vault_id == v.vault_id

    def test_picks_vault_that_resolves_all_tokens(self, engine, vaults_dir):
        v1 = Vault.create("a.md", vaults_dir=vaults_dir)
        engine.mask_text("Zebulon Quarkfield.", v1)  # only PERSON_001
        v1.save()
        v2 = Vault.create("b.md", vaults_dir=vaults_dir)
        masked2 = engine.mask_text("Zebulon Quarkfield of Vortexia Dynamics.", v2)
        v2.save()

        # text containing ORG_001 + PERSON_001 must match v2, not v1
        found = find_vault_for_text(masked2, vaults_dir=vaults_dir)
        assert found.vault_id == v2.vault_id

    def test_no_match_returns_none(self, vaults_dir):
        assert find_vault_for_text("⟦PERSON_099⟧ text", vaults_dir=vaults_dir) is None

    def test_no_tokens_returns_none(self, vaults_dir):
        assert find_vault_for_text("plain text", vaults_dir=vaults_dir) is None
