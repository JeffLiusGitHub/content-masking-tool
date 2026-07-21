"""Milestone 7 tests: deny-list loader — first-run copy, live reload,
encoding tolerance. TESTPLAN.md section 4.7.
"""
from maskingtool.denylist.loader import (
    ensure_user_denylists,
    load_deny_lists,
    read_terms_csv,
)


class TestFirstRunCopy:
    def test_samples_copied_when_absent(self, tmp_path):
        paths = ensure_user_denylists(denylist_dir=tmp_path)
        assert paths["ORG"].name == "companies.csv"
        assert paths["PERSON"].name == "people.csv"
        assert paths["ORG"].exists() and paths["PERSON"].exists()
        # shipped templates are instruction-only: NO fake placeholder names
        assert read_terms_csv(paths["ORG"]) == []
        assert read_terms_csv(paths["PERSON"]) == []
        # ...but they do carry usage instructions as comments
        assert "#" in paths["PERSON"].read_text(encoding="utf-8")

    def test_existing_files_never_overwritten(self, tmp_path):
        (tmp_path / "companies.csv").write_text(
            "name\nMy Real Company\n", encoding="utf-8"
        )
        paths = ensure_user_denylists(denylist_dir=tmp_path)
        terms = read_terms_csv(paths["ORG"])
        assert terms == ["My Real Company"]  # user's edits preserved


class TestLiveReload:
    def test_edit_takes_effect_without_restart(self, tmp_path):
        lists_before = load_deny_lists(denylist_dir=tmp_path)
        assert "Freshly Added Co" not in lists_before["ORG"]

        companies = tmp_path / "companies.csv"
        companies.write_text(
            companies.read_text(encoding="utf-8") + "Freshly Added Co\n",
            encoding="utf-8",
        )
        lists_after = load_deny_lists(denylist_dir=tmp_path)
        assert "Freshly Added Co" in lists_after["ORG"]


class TestCsvParsing:
    def test_bom_and_chinese(self, tmp_path):
        f = tmp_path / "list.csv"
        f.write_bytes("name\n张三\n华为技术有限公司\n".encode("utf-8-sig"))
        assert read_terms_csv(f) == ["张三", "华为技术有限公司"]

    def test_comments_blanks_header_skipped(self, tmp_path):
        f = tmp_path / "list.csv"
        f.write_text(
            "name\n# a comment\n\nAcme Corp\n   \nBidco Ltd\n", encoding="utf-8"
        )
        assert read_terms_csv(f) == ["Acme Corp", "Bidco Ltd"]

    def test_trailing_commas_tolerated(self, tmp_path):
        f = tmp_path / "list.csv"
        f.write_text("Acme Corp,\nBidco Ltd\n", encoding="utf-8")
        assert read_terms_csv(f) == ["Acme Corp", "Bidco Ltd"]
