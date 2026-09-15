"""The installed/frozen entry must expose a side-effect-free version probe."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from maskingtool import __version__


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = f"maskingtool-server {__version__}\n"


def _probe(module: str, data_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, "--version"],
        cwd=ROOT,
        env={**os.environ, "MASKINGTOOL_DATA_DIR": str(data_dir)},
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_version_probe_is_exact_and_side_effect_free(tmp_path: Path) -> None:
    data_dir = tmp_path / "cli-data"
    result = _probe("maskingtool", data_dir)
    assert result.returncode == 0
    assert result.stdout == EXPECTED
    assert result.stderr == ""
    assert not data_dir.exists()


def test_frozen_entry_version_probe_is_exact_and_side_effect_free(tmp_path: Path) -> None:
    data_dir = tmp_path / "server-data"
    result = _probe("maskingtool.mcp_server.server", data_dir)
    assert result.returncode == 0
    assert result.stdout == EXPECTED
    assert result.stderr == ""
    assert not data_dir.exists()
