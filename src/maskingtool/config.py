"""Per-OS app-data path resolution and user settings."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from platformdirs import user_data_dir, user_documents_dir

APP_NAME = "ContentMaskingTool"
DATA_DIR_ENV = "MASKINGTOOL_DATA_DIR"  # test isolation / advanced override
MASKED_DIR_ENV = "MASKINGTOOL_MASKED_DIR"  # test isolation / advanced override

# enable_ner defaults to True since the 2026-07-16 requirement change:
# documents contain RANDOM names, so NER is the primary detector for unknown
# names (deny-list stays highest priority for known-critical ones).
DEFAULT_SETTINGS = {
    "enable_ner": True,
    "ner_backend": "spacy",
    "expand_person_name_parts": True,
    "gui_language": "en",
    "gui_tutorial_seen": False,
}


def get_app_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    d = (
        Path(override)
        if override
        else Path(user_data_dir(APP_NAME, appauthor=False, roaming=True))
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_vaults_dir() -> Path:
    d = get_app_dir() / "vaults"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_masked_output_dir() -> Path:
    """Central folder for GUI/review-approved masked outputs.

    Defaults to <Documents>/Masked Files so users can find every masked file
    in one place; overridable via the masked_output_dir setting or env var.
    """
    override = os.environ.get(MASKED_DIR_ENV) or load_settings().get(
        "masked_output_dir"
    )
    d = (
        Path(override).expanduser()
        if override
        else Path(user_documents_dir()) / "Masked Files"
    )
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_denylist_dir() -> Path:
    d = get_app_dir() / "denylists"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_settings(app_dir: Path | None = None) -> dict:
    """User settings with defaults. Unknown keys are preserved."""
    path = (app_dir or get_app_dir()) / "settings.json"
    settings = dict(DEFAULT_SETTINGS)
    if path.exists():
        try:
            settings.update(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError):
            pass  # corrupt settings fall back to defaults rather than crash
    return settings


def save_settings(settings: dict, app_dir: Path | None = None) -> Path:
    """Atomically persist settings while preserving unknown keys."""
    directory = app_dir or get_app_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "settings.json"
    merged = load_settings(directory)
    merged.update(settings)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".settings_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path
