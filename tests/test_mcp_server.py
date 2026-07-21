"""Milestone 8 tests: MCP server — driven via the MCP SDK's in-memory client.

TESTPLAN.md section 4.8. No Claude Desktop involved; the same three tools the
frozen binary will expose are exercised end-to-end here, including
cross-"session" restore (state on disk, not in server memory).
"""
import json
from pathlib import Path

import docx
import pytest

from maskingtool.vault import TOKEN_PATTERN

FIXTURE_MD = Path(__file__).parent / "fixtures" / "sample.md"

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """Isolated app-data dir; deny-lists prefilled with the test terms.

    NER is explicitly disabled here: these tests assert the deterministic
    deny-list channel (exact entity counts); NER behavior has its own suite.
    """
    monkeypatch.setenv("MASKINGTOOL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("MASKINGTOOL_NO_GUI_SPAWN", "1")
    (tmp_path / "settings.json").write_text(
        '{"enable_ner": false}', encoding="utf-8"
    )
    denylists = tmp_path / "denylists"
    denylists.mkdir()
    (denylists / "companies.csv").write_text(
        "name\nAcme Corp\nBidco Ltd\n", encoding="utf-8"
    )
    (denylists / "people.csv").write_text(
        "name\nJohn Smith\n张三\n", encoding="utf-8"
    )
    return tmp_path


def _connect():
    from mcp.shared.memory import (
        create_connected_server_and_client_session as connect,
    )

    from maskingtool.mcp_server.server import mcp

    return connect(mcp._mcp_server)


def _payload(result) -> dict:
    if result.structuredContent is not None:
        data = result.structuredContent
        return data.get("result", data)
    return json.loads(result.content[0].text)


ALL_TERMS = ["Acme Corp", "Bidco Ltd", "John Smith", "张三"]


def _approve_review(review_id: str, doc_path: Path, out_dir: Path):
    """Simulate the human approving in the GUI: produce the masked file,
    save the vault, mark the review completed."""
    from maskingtool import review as review_mod
    from maskingtool.denylist.loader import load_deny_lists
    from maskingtool.engine import MaskingEngine
    from maskingtool.textio import read_text_exact, write_text_exact
    from maskingtool.vault import Vault

    engine = MaskingEngine(load_deny_lists(), enable_ner=False)
    vault = Vault.create(doc_path.name)
    masked = engine.mask_text(read_text_exact(doc_path), vault)
    vault.save()
    masked_file = out_dir / (doc_path.stem + ".masked.md")
    write_text_exact(masked_file, masked)
    review_mod.complete_review(review_id, {
        "masked_file_path": str(masked_file), "vault_id": vault.vault_id,
        "output_format": "markdown", "entity_counts": vault.entity_counts(),
        "manual_terms_added": [], "warnings": [],
    })
    return masked_file, vault.vault_id, masked


class TestDiscovery:
    async def test_exactly_five_tools(self, data_dir):
        async with _connect() as client:
            tools = await client.list_tools()
            names = sorted(t.name for t in tools.tools)
            assert names == [
                "get_review_result", "get_review_status", "mask_document",
                "restore_document", "restore_text",
            ]


class TestMaskDocument:
    async def test_mask_markdown_happy_path(self, data_dir):
        async with _connect() as client:
            result = await client.call_tool(
                "mask_document", {"file_path": str(FIXTURE_MD)}
            )
            assert not result.isError
            data = _payload(result)
            # mandatory review: only a handle comes back, never content
            assert data["status"] == "waiting_for_user"
            assert "masked_text" not in data

            masked_file, vault_id, _ = _approve_review(
                data["review_id"], FIXTURE_MD, data_dir
            )
            got = _payload(await client.call_tool(
                "get_review_result", {"review_id": data["review_id"]}
            ))
            assert got["vault_id"] == vault_id
            for term in ALL_TERMS:
                assert term not in got["masked_text"], f"leaked: {term}"
            assert TOKEN_PATTERN.search(got["masked_text"])

    async def test_mask_missing_file_clean_error(self, data_dir):
        async with _connect() as client:
            result = await client.call_tool(
                "mask_document", {"file_path": str(data_dir / "nope.md")}
            )
            assert result.isError
            assert "not found" in result.content[0].text.lower()

    async def test_mask_unsupported_extension(self, data_dir):
        bad = data_dir / "sheet.xlsx"
        bad.write_text("x", encoding="utf-8")
        async with _connect() as client:
            result = await client.call_tool(
                "mask_document", {"file_path": str(bad)}
            )
            assert result.isError
            assert "unsupported" in result.content[0].text.lower()


class TestRestoreText:
    async def test_cross_session_restore(self, data_dir):
        # session 1: start review, human approves
        async with _connect() as client:
            started = _payload(
                await client.call_tool(
                    "mask_document", {"file_path": str(FIXTURE_MD)}
                )
            )
        _, vault_id, masked_text = _approve_review(
            started["review_id"], FIXTURE_MD, data_dir
        )
        # session 2: a brand-new connection (server process may have restarted
        # between turns) restores using only the vault_id from disk
        async with _connect() as client:
            result = await client.call_tool(
                "restore_text",
                {"vault_id": vault_id, "masked_text": masked_text},
            )
            assert not result.isError
            data = _payload(result)
            assert data["restored_text"] == FIXTURE_MD.read_text(encoding="utf-8")
            assert data["unresolved_tokens"] == []

    async def test_restore_bad_vault_id(self, data_dir):
        async with _connect() as client:
            result = await client.call_tool(
                "restore_text",
                {"vault_id": "20990101-000000-deadbeef", "masked_text": "x"},
            )
            assert result.isError
            assert "not found" in result.content[0].text.lower()


class TestRestoreDocument:
    async def test_restore_masked_markdown_file(self, data_dir):
        async with _connect() as client:
            started = _payload(
                await client.call_tool(
                    "mask_document", {"file_path": str(FIXTURE_MD)}
                )
            )
            masked_file, vault_id, _ = _approve_review(
                started["review_id"], FIXTURE_MD, data_dir
            )
            result = await client.call_tool(
                "restore_document",
                {
                    "vault_id": vault_id,
                    "masked_file_path": str(masked_file),
                },
            )
            assert not result.isError
            data = _payload(result)
            restored = Path(data["output_file_path"]).read_text(encoding="utf-8")
            assert restored == FIXTURE_MD.read_text(encoding="utf-8")

    async def test_restore_docx_file(self, data_dir):
        # build a masked docx via the engine internals (Stage 1 has no
        # masked-docx *output* tool; restore-into-docx is still supported)
        from maskingtool.engine import MaskingEngine
        from maskingtool.parsers.docx_parser import parse_docx, write_masked_docx
        from maskingtool.vault import Vault

        original = data_dir / "orig.docx"
        d = docx.Document()
        d.add_paragraph("Acme Corp hired John Smith.")
        d.save(str(original))

        engine = MaskingEngine(
            deny_lists={"ORG": ["Acme Corp"], "PERSON": ["John Smith"]}
        )
        vault = Vault.create("orig.docx")  # uses MASKINGTOOL_DATA_DIR
        parse = parse_docx(original)
        write_masked_docx(
            parse, engine.mask_spanned(parse.spanned, vault), data_dir / "masked.docx"
        )
        vault.save()

        async with _connect() as client:
            result = await client.call_tool(
                "restore_document",
                {
                    "vault_id": vault.vault_id,
                    "masked_file_path": str(data_dir / "masked.docx"),
                },
            )
            assert not result.isError
            data = _payload(result)
            restored = docx.Document(data["output_file_path"])
            assert restored.paragraphs[0].text == "Acme Corp hired John Smith."
