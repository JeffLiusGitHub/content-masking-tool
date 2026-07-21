"""Release packaging metadata must stay synchronized across platforms."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "packaging" / "check_release_metadata.py"


def test_release_metadata_is_synchronized() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GITHUB_REF_NAME": "main"},
    )

    assert result.returncode == 0, result.stderr
    assert "Release metadata OK:" in result.stdout
    assert "5 MCP tools" in result.stdout


def test_release_metadata_rejects_a_mismatched_tag() -> None:
    result = subprocess.run(
        [sys.executable, str(CHECKER), "--expected-version", "v0.0.0"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "does not match pyproject version" in result.stderr
