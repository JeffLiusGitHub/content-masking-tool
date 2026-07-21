"""Byte-faithful text file IO.

Python's default universal-newline handling silently rewrites line endings
(\\n -> \\r\\n on Windows writes), which breaks the byte-for-byte round-trip
guarantee (INV-1). All document reads/writes go through these helpers, which
disable newline translation in both directions.
"""
from __future__ import annotations

from pathlib import Path


def read_text_exact(path: Path) -> str:
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def write_text_exact(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)
