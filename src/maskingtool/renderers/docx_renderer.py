"""Restore original values into a masked .docx (tokens -> originals).

Walks every run in body paragraphs and table cells and regex-replaces
tokens per run. Known Stage 1 limitation: a token split across runs by a
later Word edit is not reassembled.
"""
from __future__ import annotations

from pathlib import Path

import docx

from maskingtool.operators import restore_text
from maskingtool.parsers.docx_parser import _iter_block_items
from maskingtool.vault import Vault
from docx.table import Table


def restore_docx(path: Path, vault: Vault, output: Path) -> list[str]:
    document = docx.Document(str(path))
    unresolved: list[str] = []
    seen: set[str] = set()

    def _restore_paragraphs(paragraphs):
        for p in paragraphs:
            for run in p.runs:
                if run.text:
                    restored, missing = restore_text(run.text, vault)
                    if restored != run.text:
                        run.text = restored
                    for token in missing:
                        if token not in seen:
                            seen.add(token)
                            unresolved.append(token)

    for item in _iter_block_items(document):
        if isinstance(item, Table):
            for row in item.rows:
                for cell in row.cells:
                    _restore_paragraphs(cell.paragraphs)
        else:
            _restore_paragraphs([item])

    document.save(str(output))
    return unresolved
