"""User-editable deny-lists.

Sample CSVs ship inside the package; on first use they are copied to the
user's app-data dir where they can be edited with any text editor. Lists
are re-read on every masking call (no caching) so edits apply immediately.

CSV format: one term per line; optional "name" header; blank lines and
lines starting with # are ignored. UTF-8 (BOM tolerated).
"""
from __future__ import annotations

import shutil
import os
import tempfile
import json
from pathlib import Path

from maskingtool import config

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "resources" / "denylist"

FILES = {
    "ORG": "companies.csv",
    "PERSON": "people.csv",
}
SAMPLES = {
    "ORG": "companies.sample.csv",
    "PERSON": "people.sample.csv",
}


def read_terms_csv(path: Path) -> list[str]:
    terms: list[str] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        term = line.strip().strip(",")
        if not term or term.startswith("#"):
            continue
        if term.lower() in ("name", "term") and not terms:
            continue  # header row
        terms.append(term)
    return terms


def ensure_user_denylists(denylist_dir: Path | None = None) -> dict[str, Path]:
    """Copy bundled samples to the user dir on first run; never overwrite."""
    target_dir = Path(denylist_dir) if denylist_dir else config.get_denylist_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for entity_type, filename in FILES.items():
        target = target_dir / filename
        if not target.exists():
            shutil.copyfile(SAMPLES_DIR / SAMPLES[entity_type], target)
        paths[entity_type] = target
    return paths


def load_deny_lists(denylist_dir: Path | None = None) -> dict[str, list[str]]:
    paths = ensure_user_denylists(denylist_dir)
    return {entity_type: read_terms_csv(path) for entity_type, path in paths.items()}


def add_deny_term(term: str, entity_type: str, denylist_dir: Path | None = None) -> Path:
    """Atomically add one exact term to the persistent user deny-list."""
    term = term.strip()
    if not term or "\n" in term or "\r" in term:
        raise ValueError("Select a single non-empty line of text.")
    if entity_type not in FILES:
        raise ValueError(f"Unsupported entity type: {entity_type}")
    path = ensure_user_denylists(denylist_dir)[entity_type]
    if term not in read_terms_csv(path):
        existing = path.read_text(encoding="utf-8-sig")
        updated = existing + ("" if existing.endswith(("\n", "\r")) else "\n") + term + "\n"
        _atomic_text(path, updated, ".denylist_", newline="")
    manual = load_manual_terms(path.parent)
    if not any(item["term"] == term and item["entity_type"] == entity_type for item in manual):
        manual.append({"term": term, "entity_type": entity_type})
        _atomic_text(path.parent / "manual_terms.json",
                     json.dumps({"terms": manual}, ensure_ascii=False, indent=2),
                     ".manual_terms_")
    return path


def load_manual_terms(denylist_dir: Path | None = None) -> list[dict[str, str]]:
    directory = Path(denylist_dir) if denylist_dir else config.get_denylist_dir()
    path = directory / "manual_terms.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return [item for item in data.get("terms", [])
                if item.get("entity_type") in FILES and isinstance(item.get("term"), str)]
    except (OSError, json.JSONDecodeError, TypeError):
        return []


def _atomic_text(path: Path, text: str, prefix: str, newline=None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=prefix, suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline=newline) as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
