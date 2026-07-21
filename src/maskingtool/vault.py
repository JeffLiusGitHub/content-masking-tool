"""Vault: persisted, reversible token <-> original-value mapping.

One vault per masking session (typically one document). Guarantees:
- same original value -> same token, always (reverse index)
- tokens are self-describing: ⟦{ENTITY_TYPE}_{NNN}⟧
- state survives process restarts (JSON on disk, atomic writes)
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from maskingtool import config

TOKEN_PATTERN = re.compile(r"⟦(?P<type>[A-Z][A-Z_]*)_(?P<num>\d{3,})⟧")


class VaultNotFoundError(Exception):
    def __init__(self, vault_id: str):
        super().__init__(
            f"Vault '{vault_id}' was not found. It may have been deleted, or the "
            f"vault_id may be from a different machine."
        )
        self.vault_id = vault_id


def _reverse_key(original: str, entity_type: str) -> str:
    return f"{entity_type}\x00{original}"


class Vault:
    def __init__(
        self,
        vault_id: str,
        source_filename: str,
        vaults_dir: Path | None = None,
        created_at: str | None = None,
    ):
        self.vault_id = vault_id
        self.source_filename = source_filename
        self._vaults_dir = Path(vaults_dir) if vaults_dir else config.get_vaults_dir()
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self._counters: dict[str, int] = {}
        self._mappings: dict[str, dict] = {}  # token -> {original, entity_type}
        self._reverse: dict[str, str] = {}  # entity_type\x00original -> token

    # -- creation / loading ------------------------------------------------

    @classmethod
    def create(cls, source_filename: str, vaults_dir: Path | None = None) -> "Vault":
        vault_id = (
            datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        )
        return cls(vault_id, source_filename, vaults_dir=vaults_dir)

    @classmethod
    def load(cls, vault_id: str, vaults_dir: Path | None = None) -> "Vault":
        vaults_dir = Path(vaults_dir) if vaults_dir else config.get_vaults_dir()
        path = vaults_dir / f"vault_{vault_id}.json"
        if not path.exists():
            raise VaultNotFoundError(vault_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        vault = cls(
            data["vault_id"],
            data.get("source_filename", ""),
            vaults_dir=vaults_dir,
            created_at=data.get("created_at"),
        )
        vault._counters = dict(data.get("entity_counters", {}))
        vault._mappings = dict(data.get("mappings", {}))
        vault._reverse = {
            _reverse_key(m["original"], m["entity_type"]): token
            for token, m in vault._mappings.items()
        }
        return vault

    # -- core API ------------------------------------------------------------

    def get_or_create_token(self, original: str, entity_type: str) -> str:
        key = _reverse_key(original, entity_type)
        existing = self._reverse.get(key)
        if existing is not None:
            return existing
        count = self._counters.get(entity_type, 0) + 1
        self._counters[entity_type] = count
        token = f"⟦{entity_type}_{count:03d}⟧"
        self._mappings[token] = {"original": original, "entity_type": entity_type}
        self._reverse[key] = token
        return token

    def resolve(self, token: str) -> str | None:
        entry = self._mappings.get(token)
        return entry["original"] if entry else None

    def __len__(self) -> int:
        return len(self._mappings)

    def entity_counts(self) -> dict[str, int]:
        return dict(self._counters)

    # -- persistence -----------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._vaults_dir / f"vault_{self.vault_id}.json"

    def save(self) -> Path:
        self._vaults_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "vault_id": self.vault_id,
            "created_at": self.created_at,
            "source_filename": self.source_filename,
            "entity_counters": self._counters,
            "mappings": self._mappings,
        }
        # atomic write: temp file in the same directory, then os.replace
        fd, tmp = tempfile.mkstemp(
            dir=self._vaults_dir, prefix=".vault_tmp_", suffix=".json"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return self.path
