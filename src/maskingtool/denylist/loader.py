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
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock

from maskingtool import config

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "resources" / "denylist"

FILES = {
    "ORG": "companies.csv",
    "PERSON": "people.csv",
}
ENTITY_TYPES = {"ORG", "PERSON", "URL", "TEXT"}
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


def _directory(directory=None):
    return Path(directory) if directory is not None else config.get_denylist_dir()


def _lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    return FileLock(str(directory / "rules.lock"), timeout=15, is_singleton=True)


@contextmanager
def rule_transaction(denylist_dir: Path | None = None):
    """Serialize readers/writers and roll back rule changes if reanalysis fails."""
    directory = _directory(denylist_dir)
    with _lock(directory):
        paths = [directory / name for name in (*FILES.values(), "manual_terms.json", "allow_terms.json")]
        snapshot = {p: p.read_bytes() if p.exists() else None for p in paths}
        try:
            yield
        except BaseException:
            for path, data in snapshot.items():
                if data is None:
                    path.unlink(missing_ok=True)
                else:
                    _atomic_bytes(path, data)
            raise


def load_deny_lists(denylist_dir: Path | None = None) -> dict[str, list[str]]:
    directory = _directory(denylist_dir)
    with _lock(directory):
        paths = ensure_user_denylists(directory)
        lists = {entity_type: read_terms_csv(path) for entity_type, path in paths.items()}
        for item in load_manual_terms(directory):
            terms = lists.setdefault(item["entity_type"], [])
            if item["term"] not in terms:
                terms.append(item["term"])
        return lists


def add_deny_term(term: str, entity_type: str, denylist_dir: Path | None = None) -> Path:
    """Persist an exact (possibly multiline) term and reverse prior allow rules."""
    if not isinstance(term, str) or not term.strip():
        raise ValueError("Select non-empty text.")
    if entity_type not in ENTITY_TYPES:
        raise ValueError(f"Unsupported entity type: {entity_type}")
    directory = _directory(denylist_dir)
    with rule_transaction(directory):
        paths = ensure_user_denylists(directory)
        path = directory / "manual_terms.json"
        # Retain the legacy editable CSV for terms it can represent losslessly.
        if entity_type in FILES and "\n" not in term and "\r" not in term and term == term.strip().strip(",") and not term.startswith("#") and term.lower() not in {"name", "term"}:
            path = paths[entity_type]
            if term not in read_terms_csv(path):
                existing = path.read_text(encoding="utf-8-sig")
                _atomic_text(path, existing + ("" if existing.endswith(("\n", "\r")) else "\n") + term + "\n", ".denylist_", newline="")
        manual = load_manual_terms(directory)
        if not any(item["term"] == term and item["entity_type"] == entity_type for item in manual):
            manual.append({"term": term, "entity_type": entity_type})
            _save_terms(directory / "manual_terms.json", manual)
        allow = load_allow_terms(directory)
        if term in allow:
            _save_terms(directory / "allow_terms.json", [t for t in allow if t != term])
    return path


def load_manual_terms(denylist_dir: Path | None = None) -> list[dict[str, str]]:
    directory = _directory(denylist_dir)
    with _lock(directory):
        terms = _read_terms(directory / "manual_terms.json")
        if any(not isinstance(item, dict) or item.get("entity_type") not in ENTITY_TYPES or not isinstance(item.get("term"), str) or not item["term"].strip() for item in terms):
            raise ValueError("Invalid manual_terms.json; repair the local rule file.")
        return terms


def _read_terms(path):
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("terms"), list):
        raise ValueError(f"Invalid rule file: {path.name}")
    return data["terms"]


def _save_terms(path, terms):
    _atomic_text(path, json.dumps({"terms": terms}, ensure_ascii=False, indent=2), ".rules_", newline="")


def load_allow_terms(denylist_dir=None):
    directory = _directory(denylist_dir)
    with _lock(directory):
        terms = _read_terms(directory / "allow_terms.json")
        if any(not isinstance(t, str) or not t.strip() for t in terms):
            raise ValueError("Invalid allow_terms.json; repair the local rule file.")
        return terms


def remove_deny_term(term, denylist_dir=None):
    """Remove direct entries across categories; never remove a parent full name."""
    directory = _directory(denylist_dir)
    with rule_transaction(directory):
        found = any(term in terms for terms in load_deny_lists(directory).values())
        for path in ensure_user_denylists(directory).values():
            if term in read_terms_csv(path):
                lines = path.read_text(encoding="utf-8-sig").splitlines(keepends=True)
                _atomic_text(path, "".join(line for line in lines if line.strip().strip(",") != term), ".rules_", newline="")
        manual = load_manual_terms(directory)
        if any(item["term"] == term for item in manual):
            _save_terms(directory / "manual_terms.json", [item for item in manual if item["term"] != term])
        return found


def remove_allow_term(term, denylist_dir=None):
    directory = _directory(denylist_dir)
    with rule_transaction(directory):
        _save_terms(directory / "allow_terms.json", [t for t in load_allow_terms(directory) if t != term])


def undo_terms(terms, denylist_dir=None):
    """Return session-only exclusions; non-direct matches become permanent allows."""
    directory = _directory(denylist_dir)
    with rule_transaction(directory):
        temporary = set()
        allow = load_allow_terms(directory)
        for term in dict.fromkeys(terms):
            if remove_deny_term(term, directory):
                temporary.add(term)
            elif term not in allow:
                allow.append(term)
        if allow != load_allow_terms(directory):
            _save_terms(directory / "allow_terms.json", allow)
        return temporary


def rule_records(denylist_dir=None):
    directory = _directory(denylist_dir)
    with _lock(directory):
        records = []
        for kind, path in ensure_user_denylists(directory).items():
            records.extend({"list": "deny", "term": t, "entity_type": kind, "source": path.name} for t in read_terms_csv(path))
        records.extend({**item, "list": "deny", "source": "manual_terms.json"} for item in load_manual_terms(directory))
        records.extend({"list": "allow", "term": t, "entity_type": "", "source": "allow_terms.json"} for t in load_allow_terms(directory))
        return records


def _atomic_bytes(path, data):
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".rules_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


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
