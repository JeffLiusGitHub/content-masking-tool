"""Headless services shared by the drag-and-drop GUI and its tests."""
from __future__ import annotations

import difflib
import json
import os
import tempfile
import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from maskingtool import config
from maskingtool.denylist.loader import load_deny_lists
from maskingtool.denylist import loader
from maskingtool.engine import MaskingEngine
from maskingtool.pipeline import read_document, restore_file, HTML_SUFFIXES
from maskingtool.textio import write_text_exact
from maskingtool.vault import TOKEN_PATTERN, Vault


@dataclass
class HistoryRecord:
    action: str
    input_path: str
    output_path: str
    vault_id: str
    output_format: str
    created_at: str
    source_filename: str
    tokens: list[str] = field(default_factory=list)

    @classmethod
    def create(cls, action: str, input_path: Path, output_path: Path,
               vault_id: str, output_format: str, tokens: list[str]):
        return cls(action, _normal(input_path), _normal(output_path), vault_id,
                   output_format, datetime.now(timezone.utc).isoformat(),
                   input_path.name, sorted(set(tokens)))


class HistoryStore:
    def __init__(self, path: Path | None = None):
        self.path = path or (config.get_app_dir() / "gui_history.json")

    def records(self) -> list[HistoryRecord]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return [HistoryRecord(**item) for item in data.get("records", [])]
        except (OSError, json.JSONDecodeError, TypeError, KeyError):
            return []

    def append(self, record: HistoryRecord) -> None:
        records = self.records()
        records.insert(0, record)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".history_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"version": 1, "records": [asdict(r) for r in records[:500]]},
                          f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def find_output(self, path: Path) -> HistoryRecord | None:
        wanted = _normal(path)
        return next((r for r in self.records() if r.output_path == wanted), None)


class AmbiguousVaultError(Exception):
    def __init__(self, candidates: list[Vault]):
        super().__init__("Multiple vaults can resolve every token; choose one.")
        self.candidates = candidates


class NoMatchingVaultError(Exception):
    pass


def _normal(path: Path) -> str:
    return os.path.normcase(str(path.expanduser().resolve()))


def tokens_in(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in TOKEN_PATTERN.finditer(text)))


def matching_vaults(text: str, vaults_dir: Path | None = None) -> list[Vault]:
    tokens = tokens_in(text)
    if not tokens:
        return []
    directory = Path(vaults_dir) if vaults_dir else config.get_vaults_dir()
    matches: list[Vault] = []
    for path in sorted(directory.glob("vault_*.json"), reverse=True):
        vault_id = path.stem.removeprefix("vault_")
        try:
            vault = Vault.load(vault_id, vaults_dir=directory)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        if all(vault.resolve(token) is not None for token in tokens):
            matches.append(vault)
    return matches


def require_unique_vault(matches: list[Vault]) -> Vault:
    if not matches:
        raise NoMatchingVaultError("No local vault resolves every token in this file.")
    if len(matches) > 1:
        raise AmbiguousVaultError(matches)
    return matches[0]


def next_available_path(wanted: Path) -> Path:
    if not wanted.exists():
        return wanted
    for number in range(2, 10000):
        candidate = wanted.with_name(f"{wanted.stem}.{number}{wanted.suffix}")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"Too many output files beside {wanted}")


def diff_lines(before: str, after: str) -> list[tuple[str, str]]:
    rows = []
    for line in difflib.ndiff(before.splitlines(keepends=True), after.splitlines(keepends=True)):
        if line.startswith("? "):
            continue
        kind = {"- ": "delete", "+ ": "insert", "  ": "equal"}.get(line[:2], "equal")
        rows.append((kind, line[2:]))
    return rows


def readable_text(path: Path) -> str:
    return read_document(path)[0]


@dataclass
class ProcessResult:
    action: str
    input_path: Path
    output_path: Path
    vault_id: str
    entity_counts: dict[str, int]
    warnings: list[str]
    before_text: str
    after_text: str


@dataclass
class MaskPreview:
    input_path: Path
    proposed_output_path: Path
    vault: Vault
    masked_text: str
    output_format: str
    warnings: list[str]
    before_text: str
    temporary_allow: set[str] = field(default_factory=set)


def detect_file_action(path: Path, history: HistoryStore | None = None) -> str:
    path = Path(path).expanduser().resolve()
    record = (history or HistoryStore()).find_output(path)
    if record and record.action == "mask":
        return "restore"
    return "restore" if TOKEN_PATTERN.search(readable_text(path)) else "mask"


def prepare_mask_preview(path: Path, *, vaults_dir: Path | None = None,
                         vault: Vault | None = None, temporary_allow=None) -> MaskPreview:
    """Compute a mask preview without writing output, vault, or history."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    before, warnings = read_document(path)
    settings = config.load_settings()
    temporary = set(temporary_allow or ())
    with loader.rule_transaction():
        engine = MaskingEngine(load_deny_lists(), enable_ner=settings["enable_ner"],
                               expand_person_parts=settings["expand_person_name_parts"],
                               manual_terms=loader.load_manual_terms(),
                               allow_terms=loader.load_allow_terms() + list(temporary))
        vault = copy.deepcopy(vault) if vault is not None else Vault.create(path.name, vaults_dir=vaults_dir)
        masked = engine.mask_text(before, vault, html_source=path.suffix.lower() in HTML_SUFFIXES)
    proposed = next_available_path(
        config.get_masked_output_dir() / (path.stem + ".masked.md"))
    return MaskPreview(path, proposed, vault, masked, "markdown", warnings, before, temporary)


def edit_preview(preview, *, term=None, entity_type=None, undo=None, remove_rule=None):
    """Persist rules only if a complete replacement preview can be computed."""
    temporary = set(preview.temporary_allow)
    if preview.input_path.suffix.lower() in HTML_SUFFIXES:
        from maskingtool.markup import semantic_view
        if term is not None:
            term = semantic_view(term)[0]
        if undo is not None:
            undo = [semantic_view(value)[0] for value in undo]
    with loader.rule_transaction():
        if undo is not None:
            temporary.update(loader.undo_terms(undo))
        elif remove_rule is not None:
            if remove_rule["list"] == "allow":
                loader.remove_allow_term(remove_rule["term"])
            else:
                loader.remove_deny_term(remove_rule["term"])
        else:
            loader.add_deny_term(term, entity_type)
            temporary.discard(term)
        corrected = prepare_mask_preview(preview.input_path, vault=preview.vault,
                                         temporary_allow=temporary)
        if corrected.before_text != preview.before_text:
            raise ValueError("Source file changed during review; reopen it before editing rules.")
        return corrected


def active_entity_counts(text, vault):
    counts = {}
    for token in tokens_in(text):
        if vault.resolve(token) is not None:
            kind = TOKEN_PATTERN.fullmatch(token).group("type")
            counts[kind] = counts.get(kind, 0) + 1
    return counts


def commit_mask_preview(preview: MaskPreview, *,
                        history: HistoryStore | None = None) -> ProcessResult:
    """Persist a user-approved mask preview."""
    history = history or HistoryStore()
    output = next_available_path(preview.proposed_output_path)
    write_text_exact(output, preview.masked_text)
    try:
        preview.vault.save()
        history.append(HistoryRecord.create("mask", preview.input_path, output,
                                            preview.vault.vault_id,
                                            preview.output_format,
                                            tokens_in(preview.masked_text)))
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return ProcessResult("mask", preview.input_path, output, preview.vault.vault_id,
                         active_entity_counts(preview.masked_text, preview.vault), preview.warnings,
                         preview.before_text, preview.masked_text)


def process_dropped_file(path: Path, *, history: HistoryStore | None = None,
                         selected_vault_id: str | None = None,
                         vaults_dir: Path | None = None) -> ProcessResult:
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    history = history or HistoryStore()
    before = readable_text(path)
    record = history.find_output(path)
    action = detect_file_action(path, history)

    if action == "mask":
        return commit_mask_preview(prepare_mask_preview(path, vaults_dir=vaults_dir),
                                   history=history)

    if selected_vault_id:
        vault = Vault.load(selected_vault_id, vaults_dir=vaults_dir)
    elif record and record.action == "mask":
        vault = Vault.load(record.vault_id, vaults_dir=vaults_dir)
    else:
        vault = require_unique_vault(matching_vaults(before, vaults_dir))
    if any(vault.resolve(token) is None for token in tokens_in(before)):
        raise NoMatchingVaultError("The selected vault cannot resolve every token.")
    output = next_available_path(path.with_name(path.stem + ".restored" + path.suffix))
    unresolved = restore_file(path, vault, output)
    if unresolved:
        output.unlink(missing_ok=True)
        raise NoMatchingVaultError("The selected vault left unresolved tokens.")
    after = readable_text(output)
    try:
        history.append(HistoryRecord.create("restore", path, output, vault.vault_id,
                                            path.suffix.lstrip("."), tokens_in(before)))
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    return ProcessResult("restore", path, output, vault.vault_id,
                         vault.entity_counts(), [], before, after)


def remask_with_existing_vault(path: Path, vault_id: str, *,
                               history: HistoryStore | None = None,
                               vaults_dir: Path | None = None) -> ProcessResult:
    """Re-scan a source after a manual deny-list correction."""
    vault = Vault.load(vault_id, vaults_dir=vaults_dir)
    return commit_mask_preview(prepare_mask_preview(path, vault=vault), history=history)
