"""Local-only guarantees: masking needs no network, and the MCP stdio
boundary — the ONLY channel from the local process to Claude (and thus to
the cloud) — never carries pre-mask content.

Two properties:

1. No-network: with Python's socket layer disabled, the full mask -> restore
   pipeline still works for every format. If masking cannot open a socket,
   it cannot upload anything.

2. Stdio never leaks: spawn the real MCP server exactly like Claude does
   (subprocess, newline-delimited JSON-RPC over stdio), drive a mask call on
   a document salted with unique sentinel names, then assert over the RAW
   BYTES of everything the server wrote (stdout AND stderr): sentinels are
   absent in any encoding (plain, JSON-escaped, base64, url-encoded);
   masked tokens ARE present (proving we captured the right stream).
"""
import base64
import json
import os
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

import pytest

from maskingtool.engine import MaskingEngine
from maskingtool.operators import restore_text
from maskingtool.pipeline import mask_file, restore_file
from maskingtool.vault import Vault

# names that will never occur by accident in logs/paths/library output
SENTINEL_PERSON = "Zebulon Quarkfield"
SENTINEL_ORG = "Vortexia Quandary Dynamics"

DENY = {"PERSON": [SENTINEL_PERSON], "ORG": [SENTINEL_ORG]}

DOC = (
    f"# Board note\n\n{SENTINEL_PERSON} met {SENTINEL_ORG} to sign.\n"
    f"Approved by {SENTINEL_PERSON}.\n"
)


class TestNoNetworkNeeded:
    @pytest.fixture
    def no_network(self, monkeypatch):
        def _blocked(*args, **kwargs):
            raise AssertionError("network access attempted during local pipeline")

        monkeypatch.setattr(socket, "socket", _blocked)
        monkeypatch.setattr(socket, "create_connection", _blocked)
        monkeypatch.setattr(socket, "getaddrinfo", _blocked)

    def test_mask_and_restore_md_with_sockets_disabled(
        self, no_network, tmp_path, vaults_dir
    ):
        src = tmp_path / "doc.md"
        src.write_bytes(DOC.encode("utf-8"))  # byte-exact, no newline translation
        engine = MaskingEngine(deny_lists=DENY, enable_ner=False)
        vault = Vault.create("doc.md", vaults_dir=vaults_dir)

        result = mask_file(src, engine, vault, output_format="markdown")
        assert SENTINEL_PERSON not in result.masked_text
        assert SENTINEL_ORG not in result.masked_text

        restored, unresolved = restore_text(result.masked_text, vault)
        assert restored == DOC
        assert unresolved == []

    def test_docx_and_pdf_paths_with_sockets_disabled(
        self, no_network, tmp_path, vaults_dir
    ):
        import docx as docx_lib
        import pymupdf

        engine = MaskingEngine(deny_lists=DENY, enable_ner=False)

        d = docx_lib.Document()
        d.add_paragraph(f"{SENTINEL_PERSON} joined {SENTINEL_ORG}.")
        docx_path = tmp_path / "doc.docx"
        d.save(str(docx_path))
        v1 = Vault.create("doc.docx", vaults_dir=vaults_dir)
        r1 = mask_file(docx_path, engine, v1)
        assert SENTINEL_PERSON not in r1.masked_text

        pdf = pymupdf.open()
        pdf.new_page().insert_text((72, 72), f"{SENTINEL_ORG} quarterly report.")
        pdf_path = tmp_path / "doc.pdf"
        pdf.save(str(pdf_path))
        v2 = Vault.create("doc.pdf", vaults_dir=vaults_dir)
        r2 = mask_file(pdf_path, engine, v2)
        assert SENTINEL_ORG not in r2.masked_text


def _absent_in_all_encodings(haystack: bytes, sentinel: str) -> bool:
    forms = {
        sentinel.encode("utf-8"),
        json.dumps(sentinel).strip('"').encode("utf-8"),  # JSON-escaped
        urllib.parse.quote(sentinel).encode("ascii"),
        base64.b64encode(sentinel.encode("utf-8")),
    }
    hay_lower = haystack.lower()
    return all(f not in haystack and f.lower() not in hay_lower for f in forms)


class TestStdioNeverLeaksOriginals:
    def test_raw_server_output_contains_tokens_but_no_originals(self, tmp_path):
        # isolated app-data: sentinel deny-lists, default settings (NER off)
        data_dir = tmp_path / "appdata"
        (data_dir / "denylists").mkdir(parents=True)
        (data_dir / "settings.json").write_text(
            '{"enable_ner": false}', encoding="utf-8"
        )  # this test must pass on machines without the NER model
        (data_dir / "denylists" / "people.csv").write_text(
            f"name\n{SENTINEL_PERSON}\n", encoding="utf-8"
        )
        (data_dir / "denylists" / "companies.csv").write_text(
            f"name\n{SENTINEL_ORG}\n", encoding="utf-8"
        )
        doc = tmp_path / "secret.md"
        doc.write_text(DOC, encoding="utf-8")

        env = dict(os.environ)
        env["MASKINGTOOL_DATA_DIR"] = str(data_dir)
        env["MASKINGTOOL_NO_GUI_SPAWN"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        handshake = [
            {
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "leak-test", "version": "0"},
                },
            },
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
        ]

        def run_session(call):
            payload = "".join(json.dumps(r) + "\n" for r in handshake + [call])
            return subprocess.run(
                [sys.executable, "-m", "maskingtool.mcp_server.server"],
                input=payload.encode("utf-8"), capture_output=True,
                env=env, timeout=120,
            )

        # session 1: mandatory review starts; only a handle crosses stdio
        p1 = run_session({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "mask_document",
                       "arguments": {"file_path": str(doc)}},
        })
        import re

        match = re.search(rb'"review_id":\s*\\?"?([0-9]{8}-[0-9]{6}-[0-9a-f]{8})', p1.stdout)
        assert match, "review_id not found in stdout"
        rid = match.group(1).decode()

        # human approves (out-of-band, same data dir)
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("MASKINGTOOL_DATA_DIR", str(data_dir))
        try:
            from maskingtool import review as review_mod
            from maskingtool.engine import MaskingEngine
            from maskingtool.vault import Vault

            engine = MaskingEngine(deny_lists=DENY, enable_ner=False)
            vault = Vault.create(doc.name)
            masked = engine.mask_text(DOC, vault)
            vault.save()
            masked_file = tmp_path / "secret.masked.md"
            masked_file.write_bytes(masked.encode("utf-8"))
            review_mod.complete_review(rid, {
                "masked_file_path": str(masked_file),
                "vault_id": vault.vault_id, "output_format": "markdown",
                "entity_counts": vault.entity_counts(),
                "manual_terms_added": [], "warnings": [],
            })
        finally:
            monkeypatch.undo()

        # session 2: approved masked text crosses stdio — with tokens only
        p2 = run_session({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": "get_review_result",
                       "arguments": {"review_id": rid}},
        })
        assert (
            "\\u27e6PERSON_001\\u27e7".encode() in p2.stdout
            or "⟦PERSON_001⟧".encode("utf-8") in p2.stdout
        ), "approved masked text not found in stdout"

        # THE guarantee: pre-mask content never crosses the stdio boundary
        # in any session, any stream, any encoding
        for stream in (p1.stdout, p1.stderr, p2.stdout, p2.stderr):
            for sentinel in (SENTINEL_PERSON, SENTINEL_ORG):
                assert _absent_in_all_encodings(stream, sentinel), (
                    f"LEAK: '{sentinel}' crossed the stdio boundary"
                )

    def test_vault_stays_local(self, tmp_path):
        # the mapping that could reverse the masking exists ONLY under the
        # local app-data dir — nothing in the server reply references its
        # contents (only the opaque vault_id)
        data_dir = tmp_path / "appdata"
        (data_dir / "denylists").mkdir(parents=True)
        (data_dir / "settings.json").write_text(
            '{"enable_ner": false}', encoding="utf-8"
        )
        (data_dir / "denylists" / "people.csv").write_text(
            f"name\n{SENTINEL_PERSON}\n", encoding="utf-8"
        )
        (data_dir / "denylists" / "companies.csv").write_text(
            "name\n", encoding="utf-8"
        )
        doc = tmp_path / "secret.md"
        doc.write_text(DOC, encoding="utf-8")

        import maskingtool.config as config
        import importlib

        old = os.environ.get(config.DATA_DIR_ENV)
        old_spawn = os.environ.get("MASKINGTOOL_NO_GUI_SPAWN")
        os.environ[config.DATA_DIR_ENV] = str(data_dir)
        os.environ["MASKINGTOOL_NO_GUI_SPAWN"] = "1"
        try:
            from maskingtool import review as review_mod
            from maskingtool.engine import MaskingEngine
            from maskingtool.mcp_server import tools
            from maskingtool.vault import Vault

            started = tools.mask_document(str(doc))
            # the start reply carries only the review handle, never content
            assert SENTINEL_PERSON not in started.model_dump_json()

            engine = MaskingEngine(deny_lists=DENY, enable_ner=False)
            vault = Vault.create(doc.name)
            masked = engine.mask_text(DOC, vault)
            vault.save()
            masked_file = data_dir / "secret.masked.md"
            masked_file.write_bytes(masked.encode("utf-8"))
            review_mod.complete_review(started.review_id, {
                "masked_file_path": str(masked_file),
                "vault_id": vault.vault_id, "output_format": "markdown",
                "entity_counts": vault.entity_counts(),
                "manual_terms_added": [], "warnings": [],
            })

            result = tools.get_review_result(started.review_id)
            vault_files = list((data_dir / "vaults").glob("vault_*.json"))
            assert len(vault_files) == 1
            content = vault_files[0].read_text(encoding="utf-8")
            assert SENTINEL_PERSON in content  # mapping IS on local disk
            # ...and the tool reply exposes tokens only, not the mapping
            assert SENTINEL_PERSON not in result.model_dump_json()
        finally:
            if old is None:
                os.environ.pop(config.DATA_DIR_ENV, None)
            else:
                os.environ[config.DATA_DIR_ENV] = old
            if old_spawn is None:
                os.environ.pop("MASKINGTOOL_NO_GUI_SPAWN", None)
            else:
                os.environ["MASKINGTOOL_NO_GUI_SPAWN"] = old_spawn
