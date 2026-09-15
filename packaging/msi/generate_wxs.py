"""Generate deterministic WiX 4 source for the complete PyInstaller onedir."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path


WIX_NAMESPACE = "http://wixtoolset.org/schemas/v4/wxs"
VERSION_RE = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
VERSION_LIMITS = (255, 255, 65535)


def _tag(name: str) -> str:
    return f"{{{WIX_NAMESPACE}}}{name}"


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:28]
    return f"{prefix}_{digest}"


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
    payload_dir: Path,
    output_path: Path,
    metadata_path: Path,
    *,
    version: str,
    manufacturer: str,
    upgrade_code: str,
    product_name: str = "Content Masking Tool (Unsigned Test Only)",
) -> dict[str, object]:
    """Write WiX source and metadata, returning the metadata mapping."""

    _validate_version(version)
    payload_dir = payload_dir.resolve()
    if not payload_dir.is_dir():
        raise ValueError(f"payload directory does not exist: {payload_dir}")
    if not (payload_dir / "maskingtool-server.exe").is_file():
        raise ValueError("payload is missing maskingtool-server.exe")
    if not (payload_dir / "_internal").is_dir():
        raise ValueError("payload is missing the required _internal directory")

    upgrade_uuid = uuid.UUID(upgrade_code.strip("{}"))
    product_uuid = uuid.uuid5(upgrade_uuid, f"product/{version}")

    files = sorted(
        (path for path in payload_dir.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(payload_dir).as_posix().casefold(),
    )
    if not files:
        raise ValueError("payload directory is empty")
    if any(path.is_symlink() for path in files):
        raise ValueError("MSI payload must not contain symbolic links")

    ET.register_namespace("", WIX_NAMESPACE)
    wix = ET.Element(_tag("Wix"))
    package = ET.SubElement(
        wix,
        _tag("Package"),
        {
            "Name": product_name,
            "Manufacturer": manufacturer,
            "Version": version,
            "ProductCode": _guid_text(product_uuid),
            "UpgradeCode": _guid_text(upgrade_uuid),
            "Language": "1033",
            "Scope": "perMachine",
            "InstallerVersion": "500",
            "Compressed": "yes",
        },
    )
    ET.SubElement(
        package,
        _tag("MajorUpgrade"),
        {
            "DowngradeErrorMessage": "A newer version of [ProductName] is already installed.",
            "Schedule": "afterInstallInitialize",
        },
    )
    ET.SubElement(package, _tag("MediaTemplate"), {"EmbedCab": "yes"})
    ET.SubElement(
        package,
        _tag("SetProperty"),
        {
            "Id": "ARPINSTALLLOCATION",
            "Value": "[SERVERFOLDER]",
            "After": "CostFinalize",
            "Sequence": "execute",
        },
    )
    ET.SubElement(
        package,
        _tag("Property"),
        {
            "Id": "ARPCOMMENTS",
            "Value": "UNSIGNED TEST ONLY - not for production deployment",
        },
    )

    standard = ET.SubElement(package, _tag("StandardDirectory"), {"Id": "ProgramFiles64Folder"})
    product_dir = ET.SubElement(
        standard,
        _tag("Directory"),
        {"Id": "PRODUCTFOLDER", "Name": "Content Masking Tool"},
    )
    server_dir = ET.SubElement(
        product_dir,
        _tag("Directory"),
        {"Id": "SERVERFOLDER", "Name": "maskingtool-server"},
    )
    directories: dict[Path, ET.Element] = {Path(): server_dir}
    component_ids: list[str] = []

    for file_path in files:
        relative = file_path.relative_to(payload_dir)
        parent = relative.parent
        current = Path()
        for part in parent.parts:
            child = current / part
            if child not in directories:
                directories[child] = ET.SubElement(
                    directories[current],
                    _tag("Directory"),
                    {"Id": _stable_id("dir", child.as_posix()), "Name": part},
                )
            current = child

        relative_key = relative.as_posix().casefold()
        component_id = _stable_id("cmp", relative_key)
        component_ids.append(component_id)
        component = ET.SubElement(
            directories[parent],
            _tag("Component"),
            {
                "Id": component_id,
                "Guid": _guid_text(uuid.uuid5(upgrade_uuid, f"component/{relative_key}")),
                "Bitness": "always64",
            },
        )
        ET.SubElement(
            component,
            _tag("File"),
            {
                "Id": _stable_id("fil", relative_key),
                "Source": str(file_path),
                "KeyPath": "yes",
            },
        )

    feature = ET.SubElement(
        package,
        _tag("Feature"),
        {"Id": "MainFeature", "Title": "Content Masking Tool", "Level": "1"},
    )
    for component_id in component_ids:
        ET.SubElement(feature, _tag("ComponentRef"), {"Id": component_id})

    ET.indent(wix, space="  ")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(wix).write(output_path, encoding="utf-8", xml_declaration=True)

    metadata: dict[str, object] = {
        "packageType": "msi",
        "testOnly": True,
        "version": version,
        "architecture": "x64",
        "manufacturer": manufacturer,
        "publisher": manufacturer,
        "productCode": _guid_text(product_uuid),
        "upgradeCode": _guid_text(upgrade_uuid),
        "installLocation": r"%ProgramFiles%\Content Masking Tool\maskingtool-server",
        "versionProbe": (
            r"%ProgramFiles%\Content Masking Tool\maskingtool-server\maskingtool-server.exe "
            r"--version"
        ),
        "silentInstall": "msiexec /i <msi> /qn /norestart /log <install-log>",
        "managedUninstall": (
            f"msiexec /x {_guid_text(product_uuid)} /qn /norestart /log <uninstall-log>"
        ),
        "payloadFileCount": len(files),
    }
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--upgrade-code", required=True)
    args = parser.parse_args()
    generate(
        args.payload_dir,
        args.output,
        args.metadata,
        version=args.version,
        manufacturer=args.manufacturer,
        upgrade_code=args.upgrade_code,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
