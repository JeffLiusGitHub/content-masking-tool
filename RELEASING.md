# Building release artifacts

Release artifacts must be reproducible from a clean checkout. The build must
not depend on `.mcp.json`, an existing `.venv`, user AppData, local vaults, or
custom deny-lists.

## Prerequisites

- `uv` on `PATH`
- Node.js with `npm` on `PATH`
- Windows for the Windows build; macOS for the macOS build

Python and packaging dependencies are locked by `uv.lock` and
`packaging/mcpb/package-lock.json`. The build scripts install both sets of
locked dependencies automatically. Release builds use an isolated
`.build-venv` so an existing developer `.venv` (including audit tooling) is
never modified or included accidentally.

## Before changing a release version

Update the version in all three files:

- `pyproject.toml`
- `packaging/mcpb/manifest.json`
- `packaging/mcpb/manifest.macos.json`

Then run:

```powershell
.venv\Scripts\python.exe packaging\check_release_metadata.py --expected-version v1.2.0
```

The checker also verifies that both platform manifests declare the same five
MCP tools. Release builds run this check automatically.

## Windows

From any directory in PowerShell:

```powershell
& "C:\path\to\Content masking tool\packaging\pyinstaller\build_windows.ps1"
```

The script installs locked dependencies, runs the full source test suite,
builds with PyInstaller, runs the frozen MCP smoke test, and produces:

- `dist/content-masking-tool-win.mcpb`
- `dist/maskingtool-windows-standalone.zip`
- `dist/SHA256SUMS-windows.txt`

Close any Claude session using `maskingtool-server.exe` before rebuilding,
because Windows will otherwise keep the old executable locked.

## macOS

On a macOS machine:

```bash
./packaging/pyinstaller/build_macos.sh
```

The script performs the same locked build and verification flow, then writes
architecture-specific MCPB, ZIP, and SHA-256 files under `dist/`.

PyInstaller cannot cross-compile: Windows and macOS artifacts must be produced
on their matching operating systems.

## Distribution and future CI

Do not commit `dist/`. Upload only the MCPB, standalone ZIP, and checksum file
to this repository's GitHub Releases. Network captures, vaults, user
deny-lists, AppData, and local configuration must never be release inputs.

The clean-checkout contract in this document is the prerequisite for the
Stage 2 GitHub Actions release workflow. Signing certificates and passwords,
if added later, must be stored in GitHub Secrets and never in the repository.
