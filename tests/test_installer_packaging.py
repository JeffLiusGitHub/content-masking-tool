"""Managed-installer generators must be deterministic and fail closed."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "packaging" / "msi" / "generate_wxs.py"
SPEC = importlib.util.spec_from_file_location("generate_wxs", GENERATOR)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
PKG_METADATA_GENERATOR = ROOT / "packaging" / "pkg" / "generate_pkg_metadata.py"
PKG_SPEC = importlib.util.spec_from_file_location(
    "generate_pkg_metadata", PKG_METADATA_GENERATOR
)
assert PKG_SPEC and PKG_SPEC.loader
PKG_MODULE = importlib.util.module_from_spec(PKG_SPEC)
PKG_SPEC.loader.exec_module(PKG_MODULE)
BOOTSTRAPPER_GENERATOR = (
    ROOT / "packaging" / "bootstrapper" / "generate_bundle_wxs.py"
)
BOOTSTRAPPER_SPEC = importlib.util.spec_from_file_location(
    "generate_bundle_wxs", BOOTSTRAPPER_GENERATOR
)
assert BOOTSTRAPPER_SPEC and BOOTSTRAPPER_SPEC.loader
BOOTSTRAPPER_MODULE = importlib.util.module_from_spec(BOOTSTRAPPER_SPEC)
BOOTSTRAPPER_SPEC.loader.exec_module(BOOTSTRAPPER_MODULE)


def _payload(root: Path) -> Path:
    payload = root / "maskingtool-server"
    (payload / "_internal" / "nested").mkdir(parents=True)
    (payload / "maskingtool-server.exe").write_bytes(b"test-exe")
    (payload / "_internal" / "runtime.dll").write_bytes(b"test-dll")
    (payload / "_internal" / "nested" / "resource.dat").write_bytes(b"data")
    return payload


def test_wix_source_contains_complete_payload_and_is_deterministic(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    first_wxs = tmp_path / "first.wxs"
    first_metadata = tmp_path / "first.json"
    second_wxs = tmp_path / "second.wxs"
    second_metadata = tmp_path / "second.json"
    kwargs = {
        "version": "1.2.0",
        "manufacturer": "UNSIGNED TEST ONLY",
        "upgrade_code": "{E63074D2-2E07-5A50-A16C-8E5B94A6A94A}",
    }

    first = MODULE.generate(payload, first_wxs, first_metadata, **kwargs)
    second = MODULE.generate(payload, second_wxs, second_metadata, **kwargs)

    assert first["productCode"] == second["productCode"]
    assert first["payloadFileCount"] == 3
    assert first_wxs.read_bytes() == second_wxs.read_bytes()
    source = first_wxs.read_text(encoding="utf-8")
    assert "maskingtool-server.exe" in source
    assert "runtime.dll" in source
    assert "resource.dat" in source
    assert 'Scope="perMachine"' in source
    assert 'Bitness="always64"' in source
    assert json.loads(first_metadata.read_text(encoding="utf-8"))["testOnly"] is True
    assert first["silentInstall"].startswith("msiexec /i")
    assert first["managedUninstall"].startswith("msiexec /x")


def test_wix_source_requires_full_onedir(tmp_path: Path) -> None:
    payload = tmp_path / "maskingtool-server"
    payload.mkdir()
    (payload / "maskingtool-server.exe").write_bytes(b"test")

    with pytest.raises(ValueError, match="_internal"):
        MODULE.generate(
            payload,
            tmp_path / "out.wxs",
            tmp_path / "out.json",
            version="1.2.0",
            manufacturer="UNSIGNED TEST ONLY",
            upgrade_code="{E63074D2-2E07-5A50-A16C-8E5B94A6A94A}",
        )


def test_wix_source_can_stage_claude_extension(tmp_path: Path) -> None:
    extension = tmp_path / "content-masking-tool-win.mcpb"
    extension.write_bytes(b"test-mcpb")
    wxs = tmp_path / "with-extension.wxs"
    metadata = tmp_path / "with-extension.json"

    result = MODULE.generate(
        _payload(tmp_path),
        wxs,
        metadata,
        version="1.2.1",
        manufacturer="UNSIGNED TEST ONLY",
        upgrade_code="{E63074D2-2E07-5A50-A16C-8E5B94A6A94A}",
        claude_extension_path=extension,
    )

    source = wxs.read_text(encoding="utf-8")
    assert 'Id="CLAUDEEXTENSIONFOLDER"' in source
    assert 'Name="content-masking-tool-win.mcpb"' in source
    assert result["claudeExtensionIncluded"] is True
    assert result["payloadFileCount"] == 4
    assert result["claudeExtensionPath"].endswith("content-masking-tool-win.mcpb")


def test_bootstrapper_opens_staged_mcpb_and_hides_child_msi(tmp_path: Path) -> None:
    msi = tmp_path / "content-masking-tool-test.msi"
    msi.write_bytes(b"test-msi")
    first_wxs = tmp_path / "first-bundle.wxs"
    first_metadata = tmp_path / "first-bundle.json"
    second_wxs = tmp_path / "second-bundle.wxs"
    second_metadata = tmp_path / "second-bundle.json"
    kwargs = {
        "version": "1.2.1",
        "manufacturer": "UNSIGNED TEST ONLY",
        "upgrade_code": "{9F7440DA-287A-5D3D-B937-D757302FF201}",
    }

    first = BOOTSTRAPPER_MODULE.generate(msi, first_wxs, first_metadata, **kwargs)
    second = BOOTSTRAPPER_MODULE.generate(msi, second_wxs, second_metadata, **kwargs)

    assert first == second
    assert first_wxs.read_bytes() == second_wxs.read_bytes()
    source = first_wxs.read_text(encoding="utf-8")
    assert "WixStandardBootstrapperApplication" in source
    assert "[ProgramFiles64Folder]Content Masking Tool" in source
    assert "content-masking-tool-win.mcpb" in source
    assert 'Visible="no"' in source
    assert first["silentInstallRegistersClaudeExtension"] is False
    assert "explicit user confirmation" in first["interactiveClaudeRegistration"]


@pytest.mark.parametrize("version", ["1.2", "1.2.3.4", "256.0.0", "1.2.3-rc.1"])
def test_wix_source_rejects_invalid_installer_versions(tmp_path: Path, version: str) -> None:
    with pytest.raises(ValueError, match="installer version"):
        MODULE.generate(
            _payload(tmp_path),
            tmp_path / "out.wxs",
            tmp_path / "out.json",
            version=version,
            manufacturer="UNSIGNED TEST ONLY",
            upgrade_code="{E63074D2-2E07-5A50-A16C-8E5B94A6A94A}",
        )


@pytest.mark.parametrize("version", ["1.2", "1.2.3.4", "256.0.0", "1.2.3-rc.1"])
def test_pkg_metadata_rejects_invalid_installer_versions(version: str) -> None:
    with pytest.raises(ValueError, match="version"):
        PKG_MODULE.validate_version(version)


def test_macos_scripts_are_test_only_and_preserve_user_data() -> None:
    build = (ROOT / "packaging" / "pkg" / "build_macos_pkg.sh").read_text()
    uninstall = (ROOT / "packaging" / "pkg" / "uninstall.sh.in").read_text()

    assert "--test-only" in build
    assert "formal PKG creation is disabled" in build
    assert "/Library/Application Support/ContentMaskingTool" in uninstall
    assert "Library/Application Support/ContentMaskingTool" not in uninstall.replace(
        "/Library/Application Support/ContentMaskingTool", ""
    )
    assert "rm -rf \"$HOME\"" not in uninstall


def test_windows_builder_refuses_unlabelled_formal_builds() -> None:
    build = (ROOT / "packaging" / "msi" / "build_windows_msi.ps1").read_text()

    assert "if (-not $TestOnly)" in build
    assert "Formal MSI creation is disabled" in build
    assert "unsigned-test-only" in build


def test_windows_bootstrapper_requires_test_mode_and_mcpb_enabled_msi() -> None:
    build = (
        ROOT / "packaging" / "bootstrapper" / "build_windows_bootstrapper.ps1"
    ).read_text()

    assert "if (-not $TestOnly)" in build
    assert "Formal bootstrapper creation is disabled" in build
    assert "claudeExtensionIncluded" in build
    assert "WixToolset.Bal.wixext/4.0.6" in build
    assert "self-signed-test-only" in build
