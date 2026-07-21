from pathlib import Path

import pytest

from maskingtool.gui_core import (
    AmbiguousVaultError,
    HistoryRecord,
    HistoryStore,
    diff_lines,
    next_available_path,
    process_dropped_file,
    remask_with_existing_vault,
    prepare_mask_preview,
    commit_mask_preview,
)
from maskingtool.runtime import choose_run_mode
from maskingtool.vault import Vault
from maskingtool import config
from maskingtool.gui import TOUR_STEP_KEYS, translated
from maskingtool.denylist.loader import add_deny_term, load_deny_lists, load_manual_terms


class _Stdin:
    def __init__(self, is_tty):
        self._is_tty = is_tty

    def isatty(self):
        return self._is_tty


def test_three_mode_router():
    assert choose_run_mode(["mask", "a.md"], _Stdin(True)) == "cli"
    assert choose_run_mode([], _Stdin(False)) == "mcp"
    assert choose_run_mode([], _Stdin(True)) == "gui"
    assert choose_run_mode([], None) == "gui"


def test_gui_language_defaults_to_english_and_persists(tmp_path):
    assert config.load_settings(tmp_path)["gui_language"] == "en"
    assert config.load_settings(tmp_path)["gui_tutorial_seen"] is False
    config.save_settings({"gui_language": "zh"}, tmp_path)
    assert config.load_settings(tmp_path)["gui_language"] == "zh"
    assert translated("en", "choose") == "Choose file"
    assert translated("zh", "choose") == "选择文件"
    assert translated("invalid", "ready") == "Ready"
    assert TOUR_STEP_KEYS == (
        "language", "drop", "diff", "select", "confirm", "terms", "history", "restore"
    )
    for language in ("en", "zh"):
        for step in TOUR_STEP_KEYS:
            assert translated(language, f"tour_{step}_title")
            assert translated(language, f"tour_{step}_body")


def test_next_available_path_never_overwrites(tmp_path):
    wanted = tmp_path / "report.masked.md"
    assert next_available_path(wanted) == wanted
    wanted.write_text("one", encoding="utf-8")
    assert next_available_path(wanted) == tmp_path / "report.masked.2.md"
    (tmp_path / "report.masked.2.md").write_text("two", encoding="utf-8")
    assert next_available_path(wanted) == tmp_path / "report.masked.3.md"


def test_history_roundtrip_and_path_lookup(tmp_path):
    store = HistoryStore(tmp_path / "history.json")
    record = HistoryRecord.create(
        action="mask", input_path=tmp_path / "source.md",
        output_path=tmp_path / "source.masked.md", vault_id="vault-1",
        output_format="markdown", tokens=["⟦PERSON_001⟧"],
    )
    store.append(record)
    loaded = HistoryStore(tmp_path / "history.json")
    assert loaded.find_output(tmp_path / "source.masked.md").vault_id == "vault-1"
    assert loaded.records()[0].tokens == ["⟦PERSON_001⟧"]


def test_corrupt_history_is_isolated(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("not json", encoding="utf-8")
    assert HistoryStore(path).records() == []


def test_diff_unicode_has_red_and_green_lines():
    rows = diff_lines("你好 Alice\n", "你好 ⟦PERSON_001⟧\n")
    assert ("delete", "你好 Alice\n") in rows
    assert ("insert", "你好 ⟦PERSON_001⟧\n") in rows


def test_ambiguous_vault_error_exposes_candidates(tmp_path):
    for name in ("a", "b"):
        vault = Vault.create(name + ".md", vaults_dir=tmp_path)
        vault.get_or_create_token("Alice", "PERSON")
        vault.save()
    from maskingtool.gui_core import matching_vaults

    matches = matching_vaults("⟦PERSON_001⟧", tmp_path)
    assert len(matches) == 2
    with pytest.raises(AmbiguousVaultError):
        from maskingtool.gui_core import require_unique_vault
        require_unique_vault(matches)


def test_process_drop_masks_then_history_restores(monkeypatch, tmp_path):
    import maskingtool.gui_core as core
    monkeypatch.setattr(core, "load_deny_lists", lambda: {"PERSON": ["Alice Example"]})
    monkeypatch.setattr(core.config, "load_settings", lambda: {
        "enable_ner": False, "expand_person_name_parts": False,
    })
    source = tmp_path / "notes.md"
    source.write_bytes(b"Alice Example approved this.\n")
    history = HistoryStore(tmp_path / "history.json")
    vaults = tmp_path / "vaults"

    masked = process_dropped_file(source, history=history, vaults_dir=vaults)
    assert masked.action == "mask"
    assert masked.output_path.name == "notes.masked.md"
    assert "Alice Example" not in masked.after_text

    restored = process_dropped_file(masked.output_path, history=history, vaults_dir=vaults)
    assert restored.action == "restore"
    assert restored.after_text == "Alice Example approved this.\n"
    assert restored.vault_id == masked.vault_id


def test_masked_output_goes_to_central_masked_dir(
        monkeypatch, tmp_path, isolated_masked_output_dir):
    import maskingtool.gui_core as core
    monkeypatch.setattr(core, "load_deny_lists", lambda: {"PERSON": ["Alice Example"]})
    monkeypatch.setattr(core.config, "load_settings", lambda: {
        "enable_ner": False, "expand_person_name_parts": False,
    })
    source_dir = tmp_path / "somewhere-else"
    source_dir.mkdir()
    source = source_dir / "notes.md"
    source.write_bytes(b"Alice Example approved this.\n")

    masked = process_dropped_file(source, history=HistoryStore(tmp_path / "h.json"),
                                  vaults_dir=tmp_path / "vaults")
    assert masked.output_path.parent == isolated_masked_output_dir
    assert masked.output_path.name == "notes.masked.md"
    assert not (source_dir / "notes.masked.md").exists()


def test_mask_preview_writes_nothing_until_confirmed(monkeypatch, tmp_path):
    import maskingtool.gui_core as core
    monkeypatch.setattr(core, "load_deny_lists", lambda: {"PERSON": ["Alice Example"]})
    monkeypatch.setattr(core.config, "load_settings", lambda: {
        "enable_ner": False, "expand_person_name_parts": False,
    })
    source = tmp_path / "approval.md"
    source.write_bytes(b"Alice Example\n")
    vaults = tmp_path / "vaults"
    history = HistoryStore(tmp_path / "history.json")

    preview = prepare_mask_preview(source, vaults_dir=vaults)
    assert "⟦PERSON_001⟧" in preview.masked_text
    assert not preview.proposed_output_path.exists()
    assert not preview.vault.path.exists()
    assert history.records() == []

    result = commit_mask_preview(preview, history=history)
    assert result.output_path.exists()
    assert preview.vault.path.exists()
    assert history.find_output(result.output_path).vault_id == preview.vault.vault_id


def test_moved_masked_file_uses_unique_token_match(monkeypatch, tmp_path):
    import maskingtool.gui_core as core
    monkeypatch.setattr(core, "load_deny_lists", lambda: {"PERSON": ["Alice Example"]})
    monkeypatch.setattr(core.config, "load_settings", lambda: {
        "enable_ner": False, "expand_person_name_parts": False,
    })
    source = tmp_path / "notes.md"
    source.write_bytes(b"Alice Example\n")
    history = HistoryStore(tmp_path / "history.json")
    vaults = tmp_path / "vaults"
    masked = process_dropped_file(source, history=history, vaults_dir=vaults)
    moved = tmp_path / "renamed.md"
    masked.output_path.rename(moved)
    restored = process_dropped_file(moved, history=history, vaults_dir=vaults)
    assert restored.after_text == "Alice Example\n"


def test_manual_term_is_persistent_idempotent_and_remasks_all_occurrences(monkeypatch, tmp_path):
    monkeypatch.setenv("MASKINGTOOL_DATA_DIR", str(tmp_path / "app"))
    config.save_settings({"enable_ner": False, "expand_person_name_parts": False})
    source = tmp_path / "review.md"
    source.write_bytes(b"Missed Name met Missed Name.\n")
    vaults = tmp_path / "vaults"
    vault = Vault.create(source.name, vaults_dir=vaults)
    vault.save()

    first_path = add_deny_term("Missed Name", "PERSON")
    second_path = add_deny_term("Missed Name", "PERSON")
    assert first_path == second_path
    assert load_deny_lists()["PERSON"].count("Missed Name") == 1
    assert load_manual_terms() == [{"term": "Missed Name", "entity_type": "PERSON"}]

    result = remask_with_existing_vault(
        source, vault.vault_id, history=HistoryStore(tmp_path / "history.json"),
        vaults_dir=vaults,
    )
    assert result.after_text.count("⟦PERSON_001⟧") == 2
    assert "Missed Name" not in result.after_text
