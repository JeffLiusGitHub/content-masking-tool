"""The restored unified preview must never persist diff decoration or duplicates."""
import pytest

from maskingtool.selection import review_diff, map_diff_selection
from maskingtool.vault import Vault


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_multiline_diff_selection_is_exact_and_deduplicates(newline):
    before = f"😀 - 原文{newline}+ 保留两个空格  "
    vault = Vault.create("test.txt")
    after = vault.get_or_create_token(before, "TEXT")
    rows = review_diff(before, after)
    assert [r.kind for r in rows] == ["delete", "delete", "insert"]
    selected = map_diff_selection(before, after, vault, rows, 0, sum(len(r.text) for r in rows))
    assert selected.text == before
    assert selected.masked_originals == [before]
    # Selection wholly inside a green token expands back to its entire value.
    green = rows[-1]
    assert map_diff_selection(before, after, vault, rows,
                              green.content_start + 2, green.content_start + 5).text == before
    with pytest.raises(ValueError, match="diff markers"):
        map_diff_selection(before, after, vault, rows, 0, 2)
    with pytest.raises(ValueError, match="diff markers"):
        map_diff_selection(before, after, vault, rows, green.content_end, green.content_end + 1)


def test_green_partial_url_and_multiple_tokens_map_to_originals():
    vault = Vault.create("test.txt")
    first = vault.get_or_create_token("Acme", "ORG")
    second = vault.get_or_create_token("Alice", "PERSON")
    before = "intro\nhttps://Acme/path\nAlice\ntail"
    after = f"intro\nhttps://{first}/path\n{second}\ntail"
    rows = review_diff(before, after)
    green = next(r for r in rows if r.kind == "insert")
    selected = map_diff_selection(before, after, vault, rows, green.content_start, green.content_end - 1)
    assert selected.text == "https://Acme/path"
    all_selected = map_diff_selection(before, after, vault, rows, 0, sum(len(r.text) for r in rows))
    assert all_selected.text == before
    assert all_selected.masked_originals == ["Acme", "Alice"]


def test_repeated_lines_and_real_diff_prefixes_keep_correct_offsets():
    vault = Vault.create("test.txt")
    token = vault.get_or_create_token("secret", "TEXT")
    before = "same\nsecret\nsame\n- real\n+ real"
    after = before.replace("secret", token)
    rows = review_diff(before, after)
    last = rows[-1]
    selected = map_diff_selection(before, after, vault, rows, last.content_start, last.content_end)
    assert selected.text == "+ real"
    assert selected.start == before.rindex("+ real")
