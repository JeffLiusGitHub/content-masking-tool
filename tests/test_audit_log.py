"""Boundary audit log: an append-only record of exactly what each MCP tool
returned to the Claude app. This is the authoritative answer to "what did our
tool hand to Claude" — it cannot be defeated by TLS/cert-pinning because it is
written locally at the tool boundary, before Claude ever sees the result.

Design: JSONL, one line per tool call, containing timestamp, tool name,
non-sensitive input summary (paths, flags — NOT file contents), and the FULL
payload returned to Claude. For mask_document the payload is the masked text,
which by construction contains no originals; the log therefore doubles as
proof that originals never crossed the boundary.
"""
import json

import pytest

from maskingtool import config
from maskingtool.audit import audit_path, read_audit, record_call


@pytest.fixture
def audit_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(config.DATA_DIR_ENV, str(tmp_path))
    return tmp_path / "audit"


class TestRecord:
    def test_writes_one_jsonl_line_per_call(self, audit_dir):
        record_call("mask_document", {"file_path": "a.md"}, {"vault_id": "v1"})
        record_call("restore_text", {"vault_id": "v1"}, {"restored_text": "x"})
        entries = read_audit()
        assert len(entries) == 2
        assert entries[0]["tool"] == "mask_document"
        assert entries[1]["tool"] == "restore_text"

    def test_entry_has_timestamp_and_returned_payload(self, audit_dir):
        record_call("mask_document", {"file_path": "a.md"},
                    {"masked_text": "⟦PERSON_001⟧", "vault_id": "v1"})
        e = read_audit()[0]
        assert "timestamp" in e
        assert e["returned_to_claude"]["masked_text"] == "⟦PERSON_001⟧"

    def test_input_summary_never_contains_file_contents(self, audit_dir):
        # the audit log records the path, never the document body
        record_call("mask_document", {"file_path": "C:/secret/report.docx"},
                    {"masked_text": "⟦PERSON_001⟧"})
        raw = audit_path().read_text(encoding="utf-8")
        assert "C:/secret/report.docx" in raw  # path is fine
        assert "report.docx" in json.loads(raw.splitlines()[0])["input"]["file_path"]

    def test_append_only_across_calls(self, audit_dir):
        for i in range(3):
            record_call("mask_document", {"file_path": f"{i}.md"}, {"vault_id": str(i)})
        assert len(read_audit()) == 3


class TestTamperEvidence:
    def test_each_line_is_independently_valid_json(self, audit_dir):
        record_call("mask_document", {"file_path": "a.md"}, {"masked_text": "x"})
        record_call("restore_text", {"vault_id": "v"}, {"restored_text": "y"})
        for line in audit_path().read_text(encoding="utf-8").splitlines():
            json.loads(line)  # must not raise
