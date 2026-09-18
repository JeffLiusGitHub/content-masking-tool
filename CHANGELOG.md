# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims
to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A test-only Windows WiX 4 Burn guided setup prototype that installs the
  complete application, stages the matching MCPB, and lets the user explicitly
  open Claude Desktop's extension-install confirmation from the success page.
  Silent setup does not edit Claude configuration or register the extension.

## [1.2.1-test.1] - 2026-09-16

> Unsigned testing prerelease for Portal/MDM import and native installer
> lifecycle validation. It is not a production-signed release.

### Added
- Unsigned-test-only native installer projects: a WiX 4 x64/per-machine MSI
  and separate macOS arm64/x86_64 PKGs, with CI lifecycle checks for layout,
  version, repeat installation, managed uninstall, and user-data retention.
- A side-effect-free `maskingtool-server --version` probe and strict canonical
  three-part installer version validation.
- Open-source project health files: `SECURITY.md` (private vulnerability / leak
  reporting), `CONTRIBUTING.md`, this changelog, and GitHub issue/PR templates.
- CI: CodeQL static analysis, Dependabot updates (uv / GitHub Actions / npm),
  and a `ruff` (blocking) + `mypy` (informational) checks workflow.
- Ruff and mypy configuration in `pyproject.toml`.
- README status badges.

### Fixed
- The runtime `__version__` now agrees with the v1.2.0 project and MCPB
  metadata instead of reporting 1.1.0.
- The macOS Intel CI target now uses the supported `macos-15-intel` runner.
- The build workflow no longer creates or mutates GitHub Releases from platform
  jobs; it has read-only repository permissions and emits only CI artifacts.
- Removed unused imports and made `zip()` calls explicit about `strict=`
  (ruff `F401`/`B905`).

### Documentation

- Documented the requirements approved on 2026-09-14 for the next-release
  managed installation pipeline: a signed per-machine Windows x64 MSI and
  signed, notarized, and stapled macOS arm64/x86_64 PKGs, while retaining the
  Windows and per-architecture macOS MCPB extension artifacts.
- Documented the planned MDM contracts for silent installation, version
  detection, upgrade, downgrade handling, checksum/signature verification,
  managed uninstall, user-data retention, and atomic release publication.
- Added planned installer and release acceptance matrices. These checks have
  not been run, and no MSI, PKG, signature, notarization, tag, or GitHub Release
  is represented as completed by this documentation update.

## [1.2.0] - 2026-07-21

### Added
- **Native macOS builds** for both Apple Silicon (arm64) and Intel (x86_64),
  each frozen with a matching uv-managed standalone CPython (Tk bundled).
- Dual-architecture macOS CI: native `macos-14` (arm64) and `macos-13` (x86_64)
  runners producing per-architecture `.mcpb`, standalone ZIP, and checksums.
- macOS installation and Claude Desktop connection instructions in the README
  (English and 中文).
- `.gitattributes` `export-ignore` rules to keep GitHub's auto-generated source
  archive lean.

### Fixed
- macOS packaging: bundle presidio's Python sources so the
  `recognizer_registry/../conf/default_recognizers.yaml` lookup resolves on
  POSIX (Windows collapsed the `..` lexically, hiding the bug).
- `tests/test_local_only.py`: no longer pre-closes the MCP server's stdin before
  `communicate()`, which raised `ValueError` on POSIX.
- macOS release artifacts are labelled by the actual interpreter architecture
  instead of `uname -m`.

### Notes
- Builds remain unsigned; macOS Gatekeeper / Windows SmartScreen prompts are
  expected. Signing and notarization are planned next.

[Unreleased]: https://github.com/JeffLiusGitHub/content-masking-tool/compare/v1.2.1-test.1...HEAD
[1.2.1-test.1]: https://github.com/JeffLiusGitHub/content-masking-tool/releases/tag/v1.2.1-test.1
[1.2.0]: https://github.com/JeffLiusGitHub/content-masking-tool/releases/tag/v1.2.0
