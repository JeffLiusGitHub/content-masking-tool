"""Scale validation: a representative 63-name list must be fully masked and
recoverable in a future session. All names here are fictional placeholders.

Covers: INV-1 (exact round-trip), INV-2 (same name -> same token),
INV-3 (zero leakage of any listed name), INV-5 (restore from disk in a
later session), plus the tricky names this list deliberately includes:
apostrophes ("Noah D'angelo"), a single-letter surname ("Robin V"), and two
people sharing a first name ("Leah Marchetti" / "Leah Okafor").
"""
import json

import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.vault import TOKEN_PATTERN, Vault

# Fictional placeholder roster (no real people).
TEAM = [
    "Cole Han", "Elena Voss", "Priya Shah", "Daniel Brooks",
    "Noah D'angelo", "Robin V", "Leah Marchetti", "Leah Okafor",
    "Rex Fen", "Fenna Cortez", "Mira Ha", "Aaron Beckett",
    "Bianca Flores", "Caleb Nguyen", "Diana Prewitt", "Ethan Marsh",
    "Farah Nasser", "Gavin Holloway", "Hana Yoon", "Iris Caldwell",
    "Jonah Rivera", "Kira Solomon", "Liam Osei", "Maya Petrova",
    "Nolan Reyes", "Olivia Grant", "Pedro Alarcon", "Quinn Dabir",
    "Rosa Linden", "Simon Vance", "Tara Isaac", "Umar Khalid",
    "Vera Lindqvist", "Wade Sutton", "Xenia Popov", "Yusuf Adeyemi",
    "Zara Mensah", "Aiden Costa", "Brielle Novak", "Cyrus Ahn",
    "Delia Moss", "Elias Toure", "Freya Bloom", "Gideon Frost",
    "Halima Yusuf", "Isaac Romano", "Jade Whitlock", "Kenji Sato",
    "Lucia Herrera", "Marco Bianchi", "Nina Falk", "Omar Haddad",
    "Paige Sterling", "Rafael Duarte", "Sonia Kaur", "Theo Lindgren",
    "Uma Balan", "Viktor Stein", "Wendy Cho", "Yara Sabbagh",
    "Zane Mercer", "Grace Abbott", "Hugo Delacroix",
]

DENY = {"PERSON": TEAM, "ORG": ["Acme Corp"]}


def _team_document() -> str:
    """A realistic meeting-notes doc that mentions every listed name."""
    lines = ["# Team Allocation Notes", ""]
    for i, name in enumerate(TEAM):
        lines.append(f"- {name} is assigned to workstream {i % 5 + 1}.")
    lines += [
        "",
        "Cole Han will review with Elena Voss and Priya Shah on Friday.",
        "Escalations go to Cole Han first, then Daniel Brooks.",
    ]
    return "\n".join(lines) + "\n"


@pytest.fixture
def engine():
    return MaskingEngine(deny_lists=DENY, enable_ner=False)


@pytest.fixture
def vault(vaults_dir):
    return Vault.create("team_notes.md", vaults_dir=vaults_dir)


class TestAllNamesMasked:
    def test_zero_leakage_all_63_names(self, engine, vault):
        masked = engine.mask_text(_team_document(), vault)
        for name in TEAM:
            assert name not in masked, f"leaked: {name}"

    def test_each_person_gets_distinct_token(self, engine, vault):
        engine.mask_text(_team_document(), vault)
        assert vault.entity_counts()["PERSON"] == len(TEAM) == 63

    def test_repeated_mentions_share_one_token(self, engine, vault):
        masked = engine.mask_text(_team_document(), vault)
        # Cole Han appears 3x (list + review line + escalation line)
        cole_tokens = [
            m.group(0)
            for m in TOKEN_PATTERN.finditer(masked)
            if vault.resolve(m.group(0)) == "Cole Han"
        ]
        assert len(cole_tokens) == 3
        assert len(set(cole_tokens)) == 1


class TestRoundTrip:
    def test_exact_round_trip(self, engine, vault):
        original = _team_document()
        masked = engine.mask_text(original, vault)
        restored, unresolved = restore_text(masked, vault)
        assert restored == original
        assert unresolved == []


class TestFutureRecovery:
    def test_restore_in_a_later_session_from_disk(self, engine, vault, vaults_dir):
        """Mask today, close everything, restore tomorrow with only the
        vault_id — the exact product promise."""
        original = _team_document()
        masked = engine.mask_text(original, vault)
        vault.save()
        vault_id = vault.vault_id
        del vault  # everything in memory is gone

        later_session_vault = Vault.load(vault_id, vaults_dir=vaults_dir)
        restored, unresolved = restore_text(masked, later_session_vault)
        assert restored == original
        assert unresolved == []

    def test_vault_file_contains_all_names(self, engine, vault, vaults_dir):
        engine.mask_text(_team_document(), vault)
        path = vault.save()
        data = json.loads(path.read_text(encoding="utf-8"))
        stored = {m["original"] for m in data["mappings"].values()}
        assert stored.issuperset(TEAM)


class TestTrickyNames:
    def test_apostrophe_name(self, engine, vault):
        masked = engine.mask_text("Please ask Noah D'angelo for the report.", vault)
        assert "D'angelo" not in masked
        restored, _ = restore_text(masked, vault)
        assert "Noah D'angelo" in restored

    def test_single_letter_surname_boundary(self, engine, vault):
        # "Robin V" matches as a full name; the bare "Robin" in "Robin Vaughn"
        # is masked too (name-part expansion), but "Vaughn" and a standalone
        # "V" stay — single-letter parts are never expanded
        masked = engine.mask_text("Robin V joined; Robin Vaughn did not.", vault)
        assert masked.startswith("⟦PERSON_")
        assert "Robin" not in masked
        assert "Vaughn" in masked
        restored, _ = restore_text(masked, vault)
        assert restored == "Robin V joined; Robin Vaughn did not."

    def test_shared_first_name_two_people(self, engine, vault):
        masked = engine.mask_text(
            "Leah Marchetti and Leah Okafor are different people. "
            "Leah alone gets its own token.",
            vault,
        )
        tokens = [m.group(0) for m in TOKEN_PATTERN.finditer(masked)]
        assert len(set(tokens)) == 3  # one per full name + one for bare "Leah"
        originals = {vault.resolve(t) for t in set(tokens)}
        assert originals == {"Leah Marchetti", "Leah Okafor", "Leah"}

    def test_substring_names_do_not_collide(self, engine, vault):
        # "Rex Fen" vs "Fenna Cortez" / "Mira Ha" vs "Cole Han":
        # overlapping fragments must not cross-fire
        text = "Rex Fen, Fenna Cortez, Mira Ha and Cole Han met."
        masked = engine.mask_text(text, vault)
        for name in ["Rex Fen", "Fenna Cortez", "Mira Ha", "Cole Han"]:
            assert name not in masked
        restored, _ = restore_text(masked, vault)
        assert restored == text
