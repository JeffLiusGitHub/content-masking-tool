"""Generate deterministic WiX 4 Burn source for the Windows setup guide."""

from __future__ import annotations

import argparse
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

WIX_NAMESPACE = "http://wixtoolset.org/schemas/v4/wxs"
BAL_NAMESPACE = "http://wixtoolset.org/schemas/v4/wxs/bal"
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VERSION_LIMITS = (255, 255, 65535)
CLAUDE_EXTENSION_INSTALL_PATH = (
    "[ProgramFiles64Folder]Content Masking Tool\\Claude Extension\\"
    "content-masking-tool-win.mcpb"
)


def _tag(name: str) -> str:
    return f"{{{WIX_NAMESPACE}}}{name}"


def _bal_tag(name: str) -> str:
    return f"{{{BAL_NAMESPACE}}}{name}"


def _guid_text(value: uuid.UUID) -> str:
    return "{" + str(value).upper() + "}"


def _validate_version(value: str) -> None:
    match = VERSION_RE.fullmatch(value)
    if not match:
        raise ValueError(f"invalid installer version: {value!r}")
    parts = tuple(int(item) for item in match.groups())
    if any(part > limit for part, limit in zip(parts, VERSION_LIMITS, strict=True)):
        raise ValueError(f"installer version exceeds MSI limits: {value!r}")


def generate(
    msi_path: Path,
    output_path: Path,
    metadata_path: Path,
    *,
    version: str,
    manufacturer: str,
    upgrade_code: str,
    signing_mode: str = "unsigned-test-only",
) -> dict[str, object]:
    """Write Burn bundle source and metadata for an MSI containing the MCPB."""

    _validate_version(version)
    msi_path = msi_path.resolve()
    if not msi_path.is_file() or msi_path.suffix.casefold() != ".msi":
        raise ValueError(f"MSI does not exist: {msi_path}")

    bundle_upgrade_uuid = uuid.UUID(upgrade_code.strip("{}"))

    ET.register_namespace("", WIX_NAMESPACE)
    ET.register_namespace("bal", BAL_NAMESPACE)
    wix = ET.Element(_tag("Wix"))
    bundle = ET.SubElement(
        wix,
        _tag("Bundle"),
        {
            "Name": "Content Masking Tool Setup (Test Only)",
            "Manufacturer": manufacturer,
            "Version": version,
            "UpgradeCode": _guid_text(bundle_upgrade_uuid),
            "Compressed": "yes",
            "DisableModify": "yes",
            "AboutUrl": "https://github.com/JeffLiusGitHub/content-masking-tool",
            "HelpUrl": "https://github.com/JeffLiusGitHub/content-masking-tool/issues",
        },
    )
    bootstrapper_application = ET.SubElement(
        bundle, _tag("BootstrapperApplication")
    )
    ET.SubElement(
        bootstrapper_application,
        _bal_tag("WixStandardBootstrapperApplication"),
        {
            "Theme": "hyperlinkLicense",
            "LicenseUrl": (
                "https://github.com/JeffLiusGitHub/content-masking-tool/blob/main/LICENSE"
            ),
            "ShowVersion": "yes",
            "SuppressOptionsUI": "yes",
            "LaunchTarget": CLAUDE_EXTENSION_INSTALL_PATH,
            "LaunchWorkingFolder": (
                r"[ProgramFiles64Folder]Content Masking Tool\Claude Extension"
            ),
        },
    )
    chain = ET.SubElement(bundle, _tag("Chain"))
    ET.SubElement(
        chain,
        _tag("MsiPackage"),
        {
            "Id": "ContentMaskingToolMsi",
            "SourceFile": str(msi_path),
            "Compressed": "yes",
            "Vital": "yes",
            "Visible": "no",
        },
    )

    ET.indent(wix, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(wix).write(output_path, encoding="utf-8", xml_declaration=True)

    metadata: dict[str, object] = {
        "packageType": "burn-bootstrapper",
        "testOnly": True,
        "version": version,
        "architecture": "x64",
        "manufacturer": manufacturer,
        "signingMode": signing_mode,
        "bundleUpgradeCode": _guid_text(bundle_upgrade_uuid),
        "chainedMsi": msi_path.name,
        "claudeExtensionPath": (
            "%ProgramFiles%\\Content Masking Tool\\Claude Extension\\"
            "content-masking-tool-win.mcpb"
        ),
        "interactiveClaudeRegistration": (
            "After installation, select Launch to open the MCPB in Claude Desktop; "
            "Claude requires explicit user confirmation."
        ),
        "silentInstall": "<setup.exe> /install /quiet /norestart /log <install-log>",
        "managedUninstall": (
            "<setup.exe> /uninstall /quiet /norestart /log <uninstall-log>"
        ),
        "silentInstallRegistersClaudeExtension": False,
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--msi", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--upgrade-code", required=True)
    parser.add_argument(
        "--signing-mode",
        choices=("unsigned-test-only", "self-signed-test-only"),
        default="unsigned-test-only",
    )
    args = parser.parse_args()
    generate(
        args.msi,
        args.output,
        args.metadata,
        version=args.version,
        manufacturer=args.manufacturer,
        upgrade_code=args.upgrade_code,
        signing_mode=args.signing_mode,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
