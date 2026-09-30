"""Exercise real Tk selections and background review mutations without screenshots."""
import time
import tkinter as tk
import os
import sys

import pytest

from maskingtool import config, gui
from maskingtool.gui_core import prepare_mask_preview, commit_mask_preview


@pytest.fixture(scope="module")
def tk_root():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk integration requires a display (run under Xvfb on Linux).")
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


@pytest.fixture
def app(monkeypatch, tk_root):
    config.save_settings({"enable_ner": False, "gui_tutorial_seen": True})
    monkeypatch.setattr(gui, "DND_FILES", None)
    application = gui.MaskingToolApp(tk_root)
    yield application
    for child in tk_root.winfo_children():
        child.destroy()


def finish_work(app):
    deadline = time.monotonic() + 15
    def check():
        if not app.busy or time.monotonic() > deadline:
            app.root.quit()
        else:
            app.root.after(10, check)
    app.root.after(10, check)
    app.root.mainloop()
    assert not app.busy


def test_real_tk_multiline_selection_undo_and_remask(app, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a: errors.append(a))
    p = tmp_path / "source.md"
    text = "😀 https://example.test/a\r\n下一行"
    p.write_bytes(text.encode("utf-8"))
    app._preview_ready(prepare_mask_preview(p))
    app._select_panel(app.diff)
    app.diff.tag_add("sel", "1.0", "end-1c")
    assert app._selection().text == text
    app._edit_rules(term=text, entity_type="TEXT")
    finish_work(app)
    assert app.diff.get("1.0", "end-1c") == "- " + text.replace("\n", "\n- ") + "\n+ ⟦TEXT_001⟧\n"
    assert app.diff.tag_ranges("delete") and app.diff.tag_ranges("insert")
    app._select_panel(app.diff)
    app.diff.tag_add("sel", "3.4", "3.7")
    assert app._selection().text == text
    app.unmask_selected()
    finish_work(app)
    assert app.current_preview.masked_text == text
    assert app.diff.get("1.0", "end-1c") == "  " + text.replace("\n", "\n  ") + "\n"
    assert not errors


def test_edit_after_confirmation_returns_to_preview_without_output(app, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a: errors.append(a))
    p = tmp_path / "source.md"
    p.write_text("https://example.test/path", encoding="utf-8")
    preview = prepare_mask_preview(p)
    app._preview_ready(preview)
    result = commit_mask_preview(preview)
    original_bytes = result.output_path.read_bytes()
    app._success(result)
    app._select_panel(app.diff)
    app.diff.tag_add("sel", "1.0", "end-1c")
    app.unmask_selected()
    finish_work(app)
    assert app.current_preview is not None
    assert app.current_preview.masked_text == "https://example.test/path"
    assert result.output_path.read_bytes() == original_bytes
    assert len(list(result.output_path.parent.glob("*.md"))) == 1
    assert str(app.confirm_button["state"]) == "normal"
    assert not errors


def token_preview(app, tmp_path):
    path = tmp_path / "tokens.txt"
    path.write_text("😀 https://example.test/a and https://example.test/b", encoding="utf-8")
    app._preview_ready(prepare_mask_preview(path))
    return tuple(str(i) for i in app.diff.tag_ranges("mask_token"))


def test_click_token_selects_whole_value_without_unmasking(app, tmp_path):
    start, end, _, _ = token_preview(app, tmp_path)
    before = app.current_preview.masked_text
    app._snap_token_selection(app.diff.index(f"{start}+3c"))
    assert app.diff.get("sel.first", "sel.last") == "⟦URL_001⟧"
    assert str(app.diff.index("sel.first")) == start
    assert str(app.diff.index("sel.last")) == end
    assert app._selection().text == "https://example.test/a"
    assert app.current_preview.masked_text == before
    assert app.diff.tag_cget("sel", "background") == "#2563eb"
    app.unmask_button.focus_set()
    app.root.update_idletasks()
    assert app.diff.get("sel.first", "sel.last") == "⟦URL_001⟧"


def test_partial_and_multiple_token_selection_expands_visibly(app, tmp_path, monkeypatch):
    errors = []
    monkeypatch.setattr(gui.messagebox, "showerror", lambda *a: errors.append(a))
    start, _, second, end = token_preview(app, tmp_path)
    app.diff.tag_add("sel", f"{start}+2c", f"{second}+4c")
    app._snap_token_selection()
    assert app.diff.get("sel.first", "sel.last") == "⟦URL_001⟧ and ⟦URL_002⟧"
    assert str(app.diff.index("sel.last")) == end
    app.unmask_selected()
    finish_work(app)
    assert app.current_preview.masked_text == app.current_preview.before_text
    assert not app.diff.tag_ranges("mask_token")
    assert not app.diff.tag_ranges("sel")
    assert not errors


def test_regular_text_and_literal_tokens_do_not_snap(app, tmp_path):
    token_preview(app, tmp_path)
    app.diff.tag_add("sel", "1.2", "1.4")
    original = tuple(str(i) for i in app.diff.tag_ranges("sel"))
    app._snap_token_selection()
    assert tuple(str(i) for i in app.diff.tag_ranges("sel")) == original
    app.diff.tag_remove("sel", "1.0", "end")
    app._snap_token_selection("1.2")
    assert not app.diff.tag_ranges("sel")
    app._show_diff("⟦URL_001⟧", "⟦URL_001⟧")
    assert not app.diff.tag_ranges("mask_token")


def test_mouse_click_and_drag_use_native_tk_bindings(app, tmp_path):
    start, end, second, _ = token_preview(app, tmp_path)
    app.root.deiconify()
    app.root.update()
    try:
        x, y, w, h = app.diff.bbox(f"{start}+3c")
        app.diff.event_generate("<ButtonPress-1>", x=x + w // 2, y=y + h // 2)
        app.diff.event_generate("<ButtonRelease-1>", x=x + w // 2, y=y + h // 2)
        app.root.update()
        assert app.diff.get("sel.first", "sel.last") == "⟦URL_001⟧"
        # A new click on ordinary text clears the previous token highlight.
        x, y, w, h = app.diff.bbox(f"{end}+2c")
        app.diff.event_generate("<ButtonPress-1>", x=x + w // 2, y=y + h // 2)
        app.diff.event_generate("<ButtonRelease-1>", x=x + w // 2, y=y + h // 2)
        app.root.update()
        assert not app.diff.tag_ranges("sel")
        # Native reverse drag touching parts of both tokens expands both.
        x1, y1, _, h1 = app.diff.bbox(f"{second}+4c")
        x2, y2, _, h2 = app.diff.bbox(f"{start}+3c")
        app.diff.event_generate("<ButtonPress-1>", x=x1, y=y1 + h1 // 2)
        app.diff.event_generate("<B1-Motion>", x=x2, y=y2 + h2 // 2)
        app.diff.event_generate("<ButtonRelease-1>", x=x2, y=y2 + h2 // 2)
        app.root.update()
        assert app.diff.get("sel.first", "sel.last") == "⟦URL_001⟧ and ⟦URL_002⟧"
    finally:
        app.root.withdraw()


def test_adjacent_tokens_select_individually(app, tmp_path):
    path = tmp_path / "adjacent.txt"
    path.write_text("AB", encoding="utf-8")
    preview = prepare_mask_preview(path)
    first = preview.vault.get_or_create_token("A", "TEXT")
    second = preview.vault.get_or_create_token("B", "PERSON")
    preview.masked_text = first + second
    app._preview_ready(preview)
    start, _ = app.token_spans[0]
    app._snap_token_selection(app.diff.index(f"{start}+3c"))
    assert app.diff.get("sel.first", "sel.last") == first
    assert app._selection().text == "A"
