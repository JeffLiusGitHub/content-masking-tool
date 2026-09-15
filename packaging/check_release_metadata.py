"""Validate release metadata before producing distributable artifacts."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = (
    ROOT / "packaging" / "mcpb" / "manifest.json",
    ROOT / "packaging" / "mcpb" / "manifest.macos.json",
)
EXPECTED_TOOLS = (
    "mask_document",
    "get_review_status",
    "get_review_result",
    "restore_text",
    "restore_document",
)
EXPECTED_LICENSE = "AGPL-3.0-only"
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
MSI_VERSION_LIMITS = (255, 255, 65535)


def _read_project_metadata() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]


def _read_manifest(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_runtime_version() -> str:
    source = (ROOT / "src" / "maskingtool" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']\s*$', source, re.MULTILINE)
    if not match:
        raise ValueError("src/maskingtool/__init__.py has no literal __version__")
    return match.group(1)


def validate_installer_version(version: str) -> tuple[int, int, int]:
    """Validate strict SemVer-to-MSI three-part version compatibility."""

    match = VERSION_RE.fullmatch(version)
    if not match:
        raise ValueError(
            f"version {version!r} must be exactly MAJOR.MINOR.PATCH with no "
            "leading zeroes, prerelease, build metadata, or fourth field"
        )
    parts = tuple(int(value) for value in match.groups())
    if any(value > limit for value, limit in zip(parts, MSI_VERSION_LIMITS, strict=True)):
        raise ValueError(
            f"version {version!r} exceeds MSI limits "
            "(major/minor <= 255, patch <= 65535)"
        )
    return parts


def validate_release_metadata(expected_version: str | None = None) -> tuple[str, int]:
    """Return the validated version and tool count, or raise ValueError."""

    project = _read_project_metadata()
    project_version = project["version"]
    errors: list[str] = []

    try:
        validate_installer_version(project_version)
    except ValueError as exc:
        errors.append(str(exc))

    runtime_version = _read_runtime_version()
    if runtime_version != project_version:
        errors.append(
            f"runtime version {runtime_version!r} does not match "
            f"pyproject version {project_version!r}"
        )

    if project.get("license") != EXPECTED_LICENSE:
        errors.append(
            f"pyproject license {project.get('license')!r} does not match "
            f"{EXPECTED_LICENSE!r}"
        )

    if expected_version:
        normalized = expected_version.removeprefix("v")
        if normalized != project_version:
            errors.append(
                f"release version {expected_version!r} does not match "
                f"pyproject version {project_version!r}"
            )

    for path in MANIFESTS:
        manifest = _read_manifest(path)
        if manifest.get("version") != project_version:
            errors.append(
                f"{path.relative_to(ROOT)} version {manifest.get('version')!r} "
                f"does not match pyproject version {project_version!r}"
            )

        if manifest.get("license") != EXPECTED_LICENSE:
            errors.append(
                f"{path.relative_to(ROOT)} license {manifest.get('license')!r} "
                f"does not match {EXPECTED_LICENSE!r}"
            )

        tool_names = tuple(tool.get("name") for tool in manifest.get("tools", []))
        if tool_names != EXPECTED_TOOLS:
            errors.append(
                f"{path.relative_to(ROOT)} tools {tool_names!r} "
                f"do not match {EXPECTED_TOOLS!r}"
            )

    package_json = _read_manifest(ROOT / "packaging" / "mcpb" / "package.json")
    if package_json.get("license") != EXPECTED_LICENSE:
        errors.append(
            f"packaging/mcpb/package.json license {package_json.get('license')!r} "
            f"does not match {EXPECTED_LICENSE!r}"
        )

    if errors:
        raise ValueError("\n".join(errors))

    return project_version, len(EXPECTED_TOOLS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-version",
        help="optional release tag/version to compare with project metadata",
    )
    args = parser.parse_args()
    github_ref = os.environ.get("GITHUB_REF_NAME")
    inferred_tag = github_ref if github_ref and github_ref.startswith("v") else None
    expected_version = args.expected_version or inferred_tag

    try:
        version, tool_count = validate_release_metadata(expected_version)
    except (KeyError, OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"Release metadata validation failed:\n{exc}", file=sys.stderr)
        return 1

    print(
        f"Release metadata OK: v{version}, {tool_count} MCP tools, "
        f"{EXPECTED_LICENSE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
