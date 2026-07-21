#!/usr/bin/env bash
# Build the native macOS onedir binary, MCPB, standalone ZIP, and checksums.
# Must run on macOS; PyInstaller cannot cross-compile from Windows.
# Clean-machine prerequisites: uv and Node.js/npm on PATH.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST="$ROOT/dist"
MCPB_ROOT="$ROOT/packaging/mcpb"
BUILD_VENV="$ROOT/.build-venv"
PYTHON="$BUILD_VENV/bin/python"
ARCH="$(uname -m)"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "ERROR: build_macos.sh must run on macOS." >&2
  exit 1
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "ERROR: uv is required. Install it from https://astral.sh/uv" >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: Node.js/npm is required to pack the MCPB extension." >&2
  exit 1
fi

echo "== 1/9 Install locked Python dependencies =="
export UV_PROJECT_ENVIRONMENT="$BUILD_VENV"
uv sync --project "$ROOT" --locked --extra dev
"$PYTHON" -c 'import tkinter, tkinterdnd2, spacy, en_core_web_sm'

echo "== 2/9 Install locked MCPB packer =="
(cd "$MCPB_ROOT" && npm ci --ignore-scripts --no-audit --no-fund)
MCPB="$MCPB_ROOT/node_modules/.bin/mcpb"
[[ -x "$MCPB" ]] || chmod +x "$MCPB"

echo "== 3/9 Validate release metadata =="
"$PYTHON" "$ROOT/packaging/check_release_metadata.py"

echo "== 4/9 Run source test suite =="
"$PYTHON" -m pytest

echo "== 5/9 PyInstaller build ($ARCH) =="
"$PYTHON" -m PyInstaller --clean --noconfirm \
  --distpath "$DIST/pyinstaller-macos-$ARCH" \
  --workpath "$DIST/build-macos-$ARCH" \
  "$SCRIPT_DIR/maskingtool.spec"

BUNDLE="$DIST/pyinstaller-macos-$ARCH/maskingtool-server"
EXE="$BUNDLE/maskingtool-server"
[[ -x "$EXE" ]] || chmod +x "$EXE"

echo "== 6/9 Smoke test frozen MCP stdio server =="
"$PYTHON" "$SCRIPT_DIR/smoke_frozen.py" "$EXE"

echo "== 7/9 Assemble production MCPB payload =="
STAGE="$DIST/mcpb-macos-$ARCH"
case "$STAGE" in
  "$DIST"/mcpb-macos-*) ;;
  *) echo "ERROR: unsafe staging path: $STAGE" >&2; exit 1 ;;
esac
rm -rf "$STAGE"
mkdir -p "$STAGE/server"
cp -R "$BUNDLE" "$STAGE/server/maskingtool-server"
cp "$MCPB_ROOT/manifest.macos.json" "$STAGE/manifest.json"

echo "== 8/9 Pack MCPB and standalone ZIP =="
MCPB_PACKAGE="$DIST/content-masking-tool-macos-$ARCH.mcpb"
"$MCPB" pack "$STAGE" "$MCPB_PACKAGE"

ZIP="$DIST/maskingtool-macos-$ARCH-standalone.zip"
rm -f "$ZIP"
ditto -c -k --sequesterRsrc --keepParent "$BUNDLE" "$ZIP"

echo "== 9/9 Generate checksums =="
CHECKSUMS="$DIST/SHA256SUMS-macos-$ARCH.txt"
shasum -a 256 "$MCPB_PACKAGE" "$ZIP" > "$CHECKSUMS"
cat "$CHECKSUMS"

echo
echo "Done:"
echo "  Local app folder : $BUNDLE"
echo "  Standalone ZIP   : $ZIP"
echo "  Claude extension : $MCPB_PACKAGE"
echo "  Checksums        : $CHECKSUMS"
