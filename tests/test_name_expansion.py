"""Name-part expansion: a bare first name ("Owen") or surname ("Bradley")
must also be masked, each distinct matched string getting its own token.
All names here are fictional placeholders.

Rules under test:
- full names still win over parts (longest match): "Sam Delgado" is ONE token
- a bare part restores to exactly itself ("Sam" -> "Sam", never guessed
  into a full name)
- multiple people sharing a first name -> distinct tokens per distinct string
- word boundaries still hold: "Sam" never fires inside "Samuel"
- single-letter parts (the "K" in "Dana K") are NOT expanded (too destructive)
- case-sensitive: lowercase "field" is not hit by the "Field" in "Marco Field"
- the expansion can be switched off
"""
import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.vault import TOKEN_PATTERN, Vault

TEAM_SUBSET = [
    "Owen Bradley", "Sam Delgado", "Sam Whitfield", "Samuel Ortega",
    "Dana K", "Marco Field", "Cole Reyes", "张三",
]
DENY = {"PERSON": TEAM_SUBSET}


@pytest.fixture
def engine():
    return MaskingEngine(deny_lists=DENY, enable_ner=False)


@pytest.fixture
def vault(vaults_dir):
    return Vault.create("t.md", vaults_dir=vaults_dir)


class TestBareParts:
    def test_bare_first_name_masked_and_restored(self, engine, vault):
        masked = engine.mask_text("Owen attended the standup.", vault)
        assert "Owen" not in masked
        restored, _ = restore_text(masked, vault)
        assert restored == "Owen attended the standup."

    def test_bare_surname_masked(self, engine, vault):
        masked = engine.mask_text("Ask Bradley about the roster.", vault)
        assert "Bradley" not in masked

    def test_bare_part_restores_to_itself_not_full_name(self, engine, vault):
        masked = engine.mask_text("Owen attended.", vault)
        token = TOKEN_PATTERN.search(masked).group(0)
        assert vault.resolve(token) == "Owen"  # never "Owen Bradley"


class TestThreeSams:
    def test_distinct_tokens_per_distinct_string(self, engine, vault):
        masked = engine.mask_text(
            "Sam Delgado and Sam Whitfield met; later Sam joined again.", vault
        )
        tokens = [m.group(0) for m in TOKEN_PATTERN.finditer(masked)]
        assert len(tokens) == 3
        assert len(set(tokens)) == 3  # three different tokens
        originals = {vault.resolve(t) for t in tokens}
        assert originals == {"Sam Delgado", "Sam Whitfield", "Sam"}

    def test_full_name_still_single_token(self, engine, vault):
        masked = engine.mask_text("Sam Delgado presented.", vault)
        assert masked == "⟦PERSON_001⟧ presented."
        assert vault.resolve("⟦PERSON_001⟧") == "Sam Delgado"

    def test_repeated_bare_sam_same_token(self, engine, vault):
        masked = engine.mask_text("Sam asked; Sam answered.", vault)
        tokens = [m.group(0) for m in TOKEN_PATTERN.finditer(masked)]
        assert len(tokens) == 2
        assert len(set(tokens)) == 1


class TestBoundariesStillHold:
    def test_sam_never_fires_inside_samuel(self, engine, vault):
        masked = engine.mask_text("Samuel Ortega and Samuel reviewed it.", vault)
        restored, _ = restore_text(masked, vault)
        assert restored == "Samuel Ortega and Samuel reviewed it."
        # bare "Samuel" was masked as its own part, not as "Sam" + "uel"
        assert "uel reviewed" not in masked

    def test_single_letter_part_not_expanded(self, engine, vault):
        # "Dana K": expanding "K" would destroy ordinary text
        masked = engine.mask_text("Plan K is risky. K stands alone.", vault)
        assert masked == "Plan K is risky. K stands alone."
        # but "Dana" alone IS masked
        masked2 = engine.mask_text("Dana approved it.", vault)
        assert "Dana" not in masked2

    def test_case_sensitive_common_word_collision(self, engine, vault):
        # "Marco Field" expands to "Field" — lowercase "field" must be untouched
        masked = engine.mask_text("The field process runs nightly.", vault)
        assert masked == "The field process runs nightly."

    def test_cjk_name_not_split(self, engine, vault):
        # CJK names have no space parts; the full name still masks
        masked = engine.mask_text("今天张三来了。", vault)
        assert "张三" not in masked


class TestToggle:
    def test_expansion_off_restores_old_behavior(self, vault):
        engine = MaskingEngine(
            deny_lists=DENY, enable_ner=False, expand_person_parts=False
        )
        text = "Owen attended; Bradley approved."
        assert engine.mask_text(text, vault) == text

    def test_expansion_only_applies_to_person(self, vaults_dir):
        # ORG lists are never expanded ("Corp" alone must not mask)
        engine = MaskingEngine(
            deny_lists={"ORG": ["Acme Corp"]}, enable_ner=False
        )
        vault = Vault.create("t.md", vaults_dir=vaults_dir)
        masked = engine.mask_text("The Corp word alone stays.", vault)
        assert masked == "The Corp word alone stays."
