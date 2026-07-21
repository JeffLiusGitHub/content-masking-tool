"""Milestone 4 tests: CLI — first runnable milestone.

`maskingtool mask sample.md -o masked.md` then `restore` must round-trip.
Tests call cli.main() directly with a tmp vaults dir.
"""
import json
from pathlib import Path

import pytest

from maskingtool.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "sample.md"


@pytest.fixture
def denylist_files(tmp_path):
    companies = tmp_path / "companies.csv"
    companies.write_text("name\nAcme Corp\nBidco Ltd\n", encoding="utf-8")
    people = tmp_path / "people.csv"
    people.write_text("name\nJohn Smith\n张三\n", encoding="utf-8")
    return companies, people


def _mask(tmp_path, vaults_dir, denylist_files, fmt="markdown"):
    companies, people = denylist_files
    out = tmp_path / ("masked.html" if fmt == "html" else "masked.md")
    result_file = tmp_path / "mask_result.json"
    rc = main(
        [
            "mask", str(FIXTURE),
            "-o", str(out),
            "--format", fmt,
            "--no-ner",  # deterministic deny-list channel; NER has its own suite
            "--companies", str(companies),
            "--people", str(people),
            "--vaults-dir", str(vaults_dir),
            "--result-json", str(result_file),
        ]
    )
    assert rc == 0
    return out, json.loads(result_file.read_text(encoding="utf-8"))


class TestMaskCommand:
    def test_mask_markdown(self, tmp_path, vaults_dir, denylist_files):
        out, info = _mask(tmp_path, vaults_dir, denylist_files)
        masked = out.read_text(encoding="utf-8")
        assert "Acme Corp" not in masked
        assert "⟦ORG_001⟧" in masked
        assert info["vault_id"]
        assert info["entity_counts"] == {"ORG": 2, "PERSON": 2}

    def test_mask_html(self, tmp_path, vaults_dir, denylist_files):
        out, info = _mask(tmp_path, vaults_dir, denylist_files, fmt="html")
        html = out.read_text(encoding="utf-8")
        assert "<h1>" in html
        assert "Acme Corp" not in html

    def test_mask_missing_file_fails_cleanly(self, tmp_path, vaults_dir, denylist_files):
        companies, people = denylist_files
        rc = main(
            [
                "mask", str(tmp_path / "nope.md"), "--no-ner",
                "--companies", str(companies),
                "--people", str(people),
                "--vaults-dir", str(vaults_dir),
            ]
        )
        assert rc != 0


class TestRestoreCommand:
    def test_cli_round_trip(self, tmp_path, vaults_dir, denylist_files):
        masked_file, info = _mask(tmp_path, vaults_dir, denylist_files)
        restored_file = tmp_path / "restored.md"
        rc = main(
            [
                "restore", str(masked_file),
                "--vault-id", info["vault_id"],
                "-o", str(restored_file),
                "--vaults-dir", str(vaults_dir),
            ]
        )
        assert rc == 0
        assert restored_file.read_text(encoding="utf-8") == FIXTURE.read_text(
            encoding="utf-8"
        )

    @pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["LF", "CRLF"])
    def test_round_trip_is_byte_exact_for_any_line_ending(
        self, tmp_path, vaults_dir, denylist_files, newline
    ):
        # write_text's default newline translation must NOT corrupt fidelity
        companies, people = denylist_files
        src = tmp_path / "input.md"
        content = f"# Notes{newline}Acme Corp met John Smith.{newline}"
        src.write_bytes(content.encode("utf-8"))

        masked_out = tmp_path / "masked.md"
        result_file = tmp_path / "info.json"
        assert main([
            "mask", str(src), "-o", str(masked_out), "--no-ner",
            "--companies", str(companies), "--people", str(people),
            "--vaults-dir", str(vaults_dir), "--result-json", str(result_file),
        ]) == 0
        info = json.loads(result_file.read_text(encoding="utf-8"))

        restored_out = tmp_path / "restored.md"
        assert main([
            "restore", str(masked_out), "--vault-id", info["vault_id"],
            "-o", str(restored_out), "--vaults-dir", str(vaults_dir),
        ]) == 0
        assert restored_out.read_bytes() == src.read_bytes()

    def test_restore_bad_vault_id_fails_cleanly(self, tmp_path, vaults_dir, denylist_files):
        masked_file, _ = _mask(tmp_path, vaults_dir, denylist_files)
        rc = main(
            [
                "restore", str(masked_file),
                "--vault-id", "20990101-000000-deadbeef",
                "--vaults-dir", str(vaults_dir),
            ]
        )
        assert rc != 0
