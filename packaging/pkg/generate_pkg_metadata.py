"""Write machine-readable metadata for an unsigned-test-only macOS PKG."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


PACKAGE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]+$")
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VERSION_LIMITS = (255, 255, 65535)
ARCHITECTURES = {"arm64", "x86_64"}


def validate_version(value: str) -> None:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError("version must be canonical MAJOR.MINOR.PATCH")
    parts = tuple(int(item) for item in match.groups())
    if any(part > limit for part, limit in zip(parts, VERSION_LIMITS, strict=True)):
        raise ValueError("version exceeds native installer limits")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--architecture", choices=sorted(ARCHITECTURES), required=True)
    parser.add_argument("--package-id", required=True)
    parser.add_argument("--payload-file-count", type=int, required=True)
    args = parser.parse_args()
    try:
        validate_version(args.version)
    except ValueError as error:
        parser.error(str(error))
    if not PACKAGE_ID_RE.fullmatch(args.package_id):
        parser.error("package id must contain only letters, digits, dots, and hyphens")
    if args.payload_file_count <= 0:
        parser.error("payload file count must be positive")

    metadata = {
        "packageType": "pkg",
        "testOnly": True,
        "version": args.version,
        "architecture": args.architecture,
        "packageIdentifier": args.package_id,
        "installLocation": "/Library/Application Support/ContentMaskingTool/maskingtool-server",
        "launcher": "/usr/local/bin/maskingtool-server",
        "uninstallHelper": "/Library/Application Support/ContentMaskingTool/uninstall.sh",
        "silentInstall": "sudo installer -pkg <pkg> -target /",
        "managedUninstall": (
            'sudo "/Library/Application Support/ContentMaskingTool/uninstall.sh"'
        ),
        "versionProbe": "/usr/local/bin/maskingtool-server --version",
        "payloadFileCount": args.payload_file_count,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
