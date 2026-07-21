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
./packaging/pyinstaller/build_macos.sh              # every arch this host can build
./packaging/pyinstaller/build_macos.sh arm64        # Apple Silicon only
./packaging/pyinstaller/build_macos.sh x86_64       # Intel only
./packaging/pyinstaller/build_macos.sh arm64 x86_64 # both, explicitly
```

The script performs the same locked build and verification flow per
architecture, then writes architecture-specific MCPB, ZIP, and SHA-256 files
under `dist/` (e.g. `content-masking-tool-macos-arm64.mcpb` and
`content-masking-tool-macos-x86_64.mcpb`).

Each architecture is built with its own uv-managed standalone CPython, so no
Homebrew `python-tk` is required — those interpreters bundle Tk. PyInstaller
produces a binary for the architecture of the interpreter it runs under, so:

- With no argument, an **Apple Silicon** host builds both `arm64` and `x86_64`
  (the Intel interpreter runs under Rosetta 2); an **Intel** host builds
  `x86_64` only.
- Building `x86_64` on Apple Silicon requires Rosetta 2:
  `softwareupdate --install-rosetta --agree-to-license`.
- `arm64` cannot be built on an Intel host — run that build on Apple Silicon.

PyInstaller cannot cross-compile between operating systems: Windows and macOS
artifacts must each be produced on their matching OS.

## Distribution and future CI

Do not commit `dist/`. Upload only the MCPB, standalone ZIP, and checksum file
to this repository's GitHub Releases. Network captures, vaults, user
deny-lists, AppData, and local configuration must never be release inputs.

The clean-checkout contract in this document is the prerequisite for the
Stage 2 GitHub Actions release workflow. Signing certificates and passwords,
if added later, must be stored in GitHub Secrets and never in the repository.
