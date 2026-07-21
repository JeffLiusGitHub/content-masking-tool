"""Headless action detection and backwards-compatible unique vault lookup."""
from __future__ import annotations

from pathlib import Path

from maskingtool.vault import TOKEN_PATTERN, Vault


def detect_action(text: str) -> str:
    return "restore" if TOKEN_PATTERN.search(text) else "mask"


def find_vault_for_text(text: str, vaults_dir: Path | None = None) -> Vault | None:
    from maskingtool.gui_core import matching_vaults

    matches = matching_vaults(text, vaults_dir)
    return matches[0] if len(matches) == 1 else None
