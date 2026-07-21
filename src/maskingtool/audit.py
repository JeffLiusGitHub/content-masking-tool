"""Append-only boundary audit log.

Records exactly what each MCP tool returned to the Claude app, locally, at the
tool boundary. This is the authoritative, tamper-evident record of what our
tool handed to Claude — independent of (and complementary to) any network-level
capture of what the Claude app then puts on the wire.

Format: JSONL under %APPDATA%\\ContentMaskingTool\\audit\\audit-YYYYMMDD.jsonl.
Never records document file CONTENTS — only paths, flags, and the returned
payload (which for mask_document is the masked text, containing no originals).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from maskingtool import config


def audit_dir() -> Path:
    d = config.get_app_dir() / "audit"
    d.mkdir(parents=True, exist_ok=True)
    return d


def audit_path(day: str | None = None) -> Path:
    day = day or datetime.now(timezone.utc).strftime("%Y%m%d")
    return audit_dir() / f"audit-{day}.jsonl"


def record_call(tool: str, input_summary: dict, returned_to_claude: dict) -> None:
    """Append one audit entry. Best-effort: auditing must never break a tool
    call, so any IO error is swallowed rather than propagated."""
    try:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool,
            "input": input_summary,
            "returned_to_claude": returned_to_claude,
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        path = audit_path()
        with open(path, "a", encoding="utf-8", newline="") as f:
            f.write(line)
    except OSError:
        pass


def read_audit(day: str | None = None) -> list[dict]:
    path = audit_path(day)
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
