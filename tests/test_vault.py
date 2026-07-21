"""Milestone 2 tests: Vault — token minting, consistency, persistence.

TESTPLAN.md section 4.1. Written BEFORE vault.py exists (TDD red phase).
All tests use tmp_path so the real %APPDATA% is never touched.
"""
import json

import pytest

from maskingtool.vault import Vault, VaultNotFoundError, TOKEN_PATTERN


@pytest.fixture
def vaults_dir(tmp_path):
    d = tmp_path / "vaults"
    d.mkdir()
    return d


@pytest.fixture
def vault(vaults_dir):
    return Vault.create(source_filename="test.md", vaults_dir=vaults_dir)


class TestTokenFormat:
    def test_first_person_token(self, vault):
        assert vault.get_or_create_token("John Smith", "PERSON") == "⟦PERSON_001⟧"

    def test_counters_independent_per_entity_type(self, vault):
        vault.get_or_create_token("John Smith", "PERSON")
        vault.get_or_create_token("Jane Doe", "PERSON")
        # ORG counter starts at 001 regardless of PERSON counter position
        assert vault.get_or_create_token("Acme Corp", "ORG") == "⟦ORG_001⟧"

    def test_token_matches_public_pattern(self, vault):
        token = vault.get_or_create_token("Acme Corp", "ORG")
        m = TOKEN_PATTERN.fullmatch(token)
        assert m is not None
        assert m.group("type") == "ORG"


class TestConsistency:
    def test_same_value_same_token(self, vault):
        t1 = vault.get_or_create_token("Acme Corp", "ORG")
        t2 = vault.get_or_create_token("Acme Corp", "ORG")
        assert t1 == t2

    def test_distinct_values_increment(self, vault):
        assert vault.get_or_create_token("Acme Corp", "ORG") == "⟦ORG_001⟧"
        assert vault.get_or_create_token("Bidco Ltd", "ORG") == "⟦ORG_002⟧"


class TestResolve:
    def test_resolve_roundtrip(self, vault):
        token = vault.get_or_create_token("Acme Corp", "ORG")
        assert vault.resolve(token) == "Acme Corp"

    def test_resolve_unicode_names(self, vault):
        for name in ["张三", "Renée O'Connor", "Müller & Söhne GmbH"]:
            token = vault.get_or_create_token(name, "PERSON")
            assert vault.resolve(token) == name

    def test_resolve_unknown_token_returns_none(self, vault):
        assert vault.resolve("⟦ORG_999⟧") is None

    def test_resolve_malformed_token_returns_none(self, vault):
        assert vault.resolve("not a token") is None
        assert vault.resolve("") is None


class TestPersistence:
    def test_save_load_roundtrip(self, vault, vaults_dir):
        t_org = vault.get_or_create_token("Acme Corp", "ORG")
        t_person = vault.get_or_create_token("张三", "PERSON")
        vault.save()

        loaded = Vault.load(vault.vault_id, vaults_dir=vaults_dir)
        assert loaded.resolve(t_org) == "Acme Corp"
        assert loaded.resolve(t_person) == "张三"

    def test_reverse_index_survives_reload(self, vault, vaults_dir):
        t1 = vault.get_or_create_token("Acme Corp", "ORG")
        vault.save()
        loaded = Vault.load(vault.vault_id, vaults_dir=vaults_dir)
        # same value must map to the SAME token after reload (INV-2 + INV-5)
        assert loaded.get_or_create_token("Acme Corp", "ORG") == t1

    def test_counters_continue_after_reload(self, vault, vaults_dir):
        vault.get_or_create_token("Acme Corp", "ORG")
        vault.save()
        loaded = Vault.load(vault.vault_id, vaults_dir=vaults_dir)
        # new value must NOT collide with the pre-reload token numbering
        assert loaded.get_or_create_token("Bidco Ltd", "ORG") == "⟦ORG_002⟧"

    def test_saved_file_is_valid_json(self, vault, vaults_dir):
        vault.get_or_create_token("Acme Corp", "ORG")
        path = vault.save()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["vault_id"] == vault.vault_id
        assert data["source_filename"] == "test.md"

    def test_repeated_save_leaves_no_temp_files(self, vault, vaults_dir):
        vault.get_or_create_token("Acme Corp", "ORG")
        vault.save()
        vault.get_or_create_token("Bidco Ltd", "ORG")
        vault.save()
        files = list(vaults_dir.iterdir())
        assert len(files) == 1
        assert files[0].suffix == ".json"

    def test_load_missing_vault_raises(self, vaults_dir):
        with pytest.raises(VaultNotFoundError):
            Vault.load("20990101-000000-deadbeef", vaults_dir=vaults_dir)
