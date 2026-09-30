"""Semantic HTML input, no networking, URL restoration and shared previews."""
import socket

from maskingtool.engine import MaskingEngine
from maskingtool.pipeline import mask_file, restore_file, read_document
from maskingtool.vault import Vault
from maskingtool.operators import restore_text


def test_html_semantic_table_links_and_inline_names(tmp_path, monkeypatch):
    def blocked(*a, **kw):
        raise AssertionError("HTML parsing must be offline")
    monkeypatch.setattr(socket, "socket", blocked)
    source = tmp_path / "schedule.html"
    source.write_text('''<h1>Schedule</h1><script>SecretScript</script><!-- SecretComment -->
      <p><b>Toyota</b> Australia &amp; partners</p><ul><li>Prepare</li></ul>
      <table><tr><th>Role</th><th>Hours</th></tr>
      <tr><td rowspan="2">Project Sponsor</td><td>1<br>2</td></tr><tr><td>3</td></tr></table>
      <a onclick="bad()" href="https://example.test/path?a=1&amp;b=2">Details</a>
      <img alt="Diagram" src="https://remote.test/image">''', encoding="utf-8")
    canonical, warnings = read_document(source)
    assert "# Schedule" in canonical and "- Prepare" in canonical
    assert canonical.count("Project Sponsor") == 2
    assert "1<br>2" in canonical and "| Role | Hours |" in canonical
    assert all(x not in canonical for x in ["SecretScript", "SecretComment", "onclick", "remote.test"])
    v = Vault.create(source.name, vaults_dir=tmp_path / "vaults")
    e = MaskingEngine({"ORG": ["Toyota Australia"]})
    result = mask_file(source, e, v)
    assert "Toyota" not in result.masked_text and "https://example" not in result.masked_text
    assert restore_text(result.masked_text, v) == (canonical, [])
    html = mask_file(source, e, v, output_format="html").masked_text
    masked = tmp_path / "out.html"
    masked.write_text(html, encoding="utf-8")
    restored = tmp_path / "restored.html"
    assert restore_file(masked, v, restored) == []
    restored_text = restored.read_text(encoding="utf-8")
    assert "<table>" in html and "⟦URL_" in html
    assert 'https://example.test/path?a=1&amp;b=2' in restored_text
    assert "Toyota Australia" in restored_text


def test_nested_table_and_colspan(tmp_path):
    p = tmp_path / "nested.htm"
    p.write_text('<table><tr><th colspan="2">Heading</th></tr><tr><td>A<table><tr><td>B</td><td>C</td></tr></table></td><td>D</td></tr></table>', encoding="utf-8")
    text, warnings = read_document(p)
    assert "| Heading | Heading |" in text
    assert "B" in text and "C" in text and "D" in text
    assert warnings


def test_html_preview_uses_same_source_and_reuses_vault(tmp_path, monkeypatch):
    from maskingtool import config
    from maskingtool.gui_core import prepare_mask_preview
    monkeypatch.setenv("MASKINGTOOL_DATA_DIR", str(tmp_path / "app"))
    config.save_settings({"enable_ner": False})
    p = tmp_path / "sample.html"
    p.write_text('<p>https://example.test/a</p>', encoding="utf-8")
    preview = prepare_mask_preview(p)
    assert preview.before_text == read_document(p)[0]
    updated = prepare_mask_preview(p, vault=preview.vault, temporary_allow={"https://example.test/a"})
    assert updated.vault.vault_id == preview.vault.vault_id
    assert updated.masked_text == updated.before_text


def test_html_entity_decoding_and_safe_restore(tmp_path):
    from bs4 import BeautifulSoup
    p = tmp_path / "entities.html"
    p.write_text('<p>A &amp; B</p><a href="https://example.test/?a=1&amp;b=2">link</a>', encoding="utf-8")
    v = Vault.create(p.name, vaults_dir=tmp_path / "vaults")
    result = mask_file(p, MaskingEngine({"ORG": ["A & B"]}), v, output_format="html")
    assert "A &amp; B" not in result.masked_text
    masked, restored = tmp_path / "masked.html", tmp_path / "restored.html"
    masked.write_text(result.masked_text, encoding="utf-8")
    restore_file(masked, v, restored)
    parsed = BeautifulSoup(restored.read_text(encoding="utf-8"), "html.parser")
    assert parsed.p.text == "A & B"
    assert parsed.a["href"] == "https://example.test/?a=1&b=2"


def test_html_cli_and_mcp_review_gate(tmp_path, monkeypatch):
    from maskingtool.cli import main
    from maskingtool import config, review
    from maskingtool.mcp_server import tools
    from maskingtool.gui_core import prepare_mask_preview, commit_mask_preview
    import pytest
    config.save_settings({"enable_ner": False})
    monkeypatch.setenv("MASKINGTOOL_NO_GUI_SPAWN", "1")
    p = tmp_path / "input.html"
    p.write_text('<p>https://example.test/secret</p>', encoding="utf-8")
    output = tmp_path / "cli.md"
    assert main(["mask", str(p), "--no-ner", "-o", str(output)]) == 0
    assert "⟦URL_001⟧" in output.read_text(encoding="utf-8")
    started = tools.mask_document(str(p))
    with pytest.raises(ValueError):
        tools.get_review_result(started.review_id)
    result = commit_mask_preview(prepare_mask_preview(p))
    review.complete_review(started.review_id, {
        "masked_file_path": str(result.output_path), "vault_id": result.vault_id,
        "entity_counts": result.entity_counts,
    })
    approved = tools.get_review_result(started.review_id)
    assert "https://example.test" not in approved.masked_text
    assert approved.entity_counts == {"URL": 1}


def test_html_restore_never_injects_original_markup(tmp_path):
    v = Vault.create("unsafe", vaults_dir=tmp_path / "vaults")
    token = v.get_or_create_token('<script>alert("x")</script>', "TEXT")
    masked, restored = tmp_path / "masked.html", tmp_path / "restored.html"
    masked.write_text("<p>" + token + "</p>", encoding="utf-8")
    restore_file(masked, v, restored)
    assert "<script>" not in restored.read_text(encoding="utf-8")


def test_html_escaped_names_match_semantically_and_restore(tmp_path):
    from bs4 import BeautifulSoup
    from maskingtool import config
    from maskingtool.gui_core import prepare_mask_preview, edit_preview
    config.save_settings({"enable_ner": False})
    p = tmp_path / "escaped.html"
    p.write_text('<p>A[B]*Lab &amp; &lt;Team&gt;</p>', encoding="utf-8")
    v = Vault.create(p.name, vaults_dir=tmp_path / "vaults")
    engine = MaskingEngine({"ORG": ["A[B]*Lab", "<Team>"]})
    result = mask_file(p, engine, v, output_format="html")
    assert "A[B]" not in result.masked_text and "Team" not in result.masked_text
    masked, restored = tmp_path / "masked.html", tmp_path / "restored.html"
    masked.write_text(result.masked_text, encoding="utf-8")
    v.save()
    restore_file(masked, Vault.load(v.vault_id, tmp_path / "vaults"), restored)
    assert BeautifulSoup(restored.read_text(encoding="utf-8"), "html.parser").p.text == "A[B]*Lab & <Team>"
    preview = prepare_mask_preview(p)
    selected = preview.before_text.rstrip("\n")
    manual = edit_preview(preview, term=selected, entity_type="TEXT")
    assert manual.masked_text == "⟦TEXT_001⟧\n"
    undone = edit_preview(manual, undo=[selected])
    assert undone.masked_text == preview.before_text


def test_same_url_in_link_and_visible_text_reuses_token(tmp_path):
    p = tmp_path / "url.html"
    url = "https://example.test/a_b?x=1&amp;y=2"
    p.write_text(f'<p>{url}</p><a href="{url}">Link</a>', encoding="utf-8")
    v = Vault.create("url", vaults_dir=tmp_path)
    result = mask_file(p, MaskingEngine({}), v)
    assert result.masked_text.count("⟦URL_001⟧") == 2
    assert v.entity_counts() == {"URL": 1}
