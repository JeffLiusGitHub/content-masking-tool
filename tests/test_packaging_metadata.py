"""Release packaging metadata must stay synchronized across platforms."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "packaging" / "check_release_metadata.py"
SPEC = importlib.util.spec_from_file_location("check_release_metadata", CHECKER)
assert SPEC and SPEC.loader
CHECKER_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKER_MODULE)
validate_installer_version = CHECKER_MODULE.validate_installer_version


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


@pytest.mark.parametrize(
    "version",
    ["1.2", "1.2.3.4", "01.2.3", "1.02.3", "1.2.03", "1.2.3-rc.1", "1.2.3+build"],
)
def test_installer_version_rejects_noncanonical_values(version: str) -> None:
    with pytest.raises(ValueError):
        validate_installer_version(version)


@pytest.mark.parametrize("version", ["256.0.0", "0.256.0", "0.0.65536"])
def test_installer_version_rejects_values_outside_msi_limits(version: str) -> None:
    with pytest.raises(ValueError, match="exceeds MSI limits"):
        validate_installer_version(version)


def test_installer_version_accepts_boundary_values() -> None:
    assert validate_installer_version("255.255.65535") == (255, 255, 65535)
