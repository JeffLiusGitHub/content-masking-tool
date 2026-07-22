#!/usr/bin/env bash
# Build macOS onedir binaries, MCPBs, standalone ZIPs, and checksums for one or
# more CPU architectures. Must run on macOS; PyInstaller cannot cross-compile
# from Windows and produces a binary for the architecture of the interpreter it
# runs under.
#
# Usage:
#   build_macos.sh                # build every architecture this host can build
#   build_macos.sh arm64          # build only Apple Silicon
#   build_macos.sh x86_64         # build only Intel
#   build_macos.sh arm64 x86_64   # build both explicitly
#
# Each architecture is built with a matching uv-managed standalone CPython.
# Those builds bundle Tk, so no Homebrew python-tk is required. An Apple
# Silicon host can also build x86_64 (the Intel interpreter runs under
# Rosetta 2); an Intel host can only build x86_64.
#
# Clean-machine prerequisites: uv and Node.js/npm on PATH (+ Rosetta 2 to build
# x86_64 on Apple Silicon: `softwareupdate --install-rosetta`).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST="$ROOT/dist"
MCPB_ROOT="$ROOT/packaging/mcpb"
HOST_ARCH="$(uname -m)"

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

# Which architectures to build. Default: every arch this host can produce.
TARGETS=("$@")
if [[ ${#TARGETS[@]} -eq 0 ]]; then
  if [[ "$HOST_ARCH" == "arm64" ]]; then
    TARGETS=(arm64 x86_64)
  else
    TARGETS=(x86_64)
  fi
fi

# Install the locked MCPB packer once; it is architecture-independent.
echo "== Install locked MCPB packer =="
(cd "$MCPB_ROOT" && npm ci --ignore-scripts --no-audit --no-fund)
MCPB="$MCPB_ROOT/node_modules/.bin/mcpb"
[[ -x "$MCPB" ]] || chmod +x "$MCPB"

SUMMARY=()

build_one() {
  local ARCH="$1"
  local UVARCH BUILD_VENV PYTHON BASE_PY REAL_ARCH

  case "$ARCH" in
    arm64)  UVARCH="aarch64" ;;
    x86_64) UVARCH="x86_64" ;;
    *) echo "ERROR: unknown architecture '$ARCH' (expected arm64 or x86_64)." >&2; exit 1 ;;
  esac

  # An Intel host cannot run an arm64 interpreter, so it cannot build arm64.
  if [[ "$HOST_ARCH" != "arm64" && "$ARCH" == "arm64" ]]; then
    echo "ERROR: cannot build arm64 on an $HOST_ARCH host; run this on Apple Silicon." >&2
    exit 1
  fi

  echo
  echo "########## Building $ARCH ##########"

  echo "== 1/9 Provision uv-managed standalone CPython ($ARCH) =="
  uv python install "cpython-3.11-macos-$UVARCH"
  BASE_PY="$(uv python find --python-preference only-managed "cpython-3.11-macos-$UVARCH")"
  # On Apple Silicon, an x86_64 interpreter needs Rosetta 2 to run.
  if ! "$BASE_PY" -c 'pass' 2>/dev/null; then
    echo "ERROR: cannot run the $ARCH interpreter ($BASE_PY)." >&2
    if [[ "$HOST_ARCH" == "arm64" && "$ARCH" == "x86_64" ]]; then
      echo "       Install Rosetta 2: softwareupdate --install-rosetta --agree-to-license" >&2
    fi
    exit 1
  fi

  echo "== 2/9 Install locked Python dependencies ($ARCH) =="
  BUILD_VENV="$ROOT/.build-venv-$ARCH"
  PYTHON="$BUILD_VENV/bin/python"
  UV_PROJECT_ENVIRONMENT="$BUILD_VENV" \
    uv sync --project "$ROOT" --locked --extra dev --python "$BASE_PY"
  "$PYTHON" -c 'import tkinter, tkinterdnd2, spacy, en_core_web_sm'
  REAL_ARCH="$("$PYTHON" -c 'import platform; print(platform.machine())')"
  if [[ "$REAL_ARCH" != "$ARCH" ]]; then
    echo "ERROR: interpreter architecture mismatch: wanted $ARCH, got $REAL_ARCH." >&2
    exit 1
  fi

  echo "== 3/9 Validate release metadata ($ARCH) =="
  "$PYTHON" "$ROOT/packaging/check_release_metadata.py"

  echo "== 4/9 Run source test suite ($ARCH) =="
  "$PYTHON" -m pytest

  echo "== 5/9 PyInstaller build ($ARCH) =="
  "$PYTHON" -m PyInstaller --clean --noconfirm \
    --distpath "$DIST/pyinstaller-macos-$ARCH" \
    --workpath "$DIST/build-macos-$ARCH" \
    "$SCRIPT_DIR/maskingtool.spec"

  local BUNDLE EXE
  BUNDLE="$DIST/pyinstaller-macos-$ARCH/maskingtool-server"
  EXE="$BUNDLE/maskingtool-server"
  [[ -x "$EXE" ]] || chmod +x "$EXE"

  echo "== 6/9 Smoke test frozen MCP stdio server ($ARCH) =="
  "$PYTHON" "$SCRIPT_DIR/smoke_frozen.py" "$EXE"

  echo "== 7/9 Assemble production MCPB payload ($ARCH) =="
  local STAGE
  STAGE="$DIST/mcpb-macos-$ARCH"
  case "$STAGE" in
    "$DIST"/mcpb-macos-*) ;;
    *) echo "ERROR: unsafe staging path: $STAGE" >&2; exit 1 ;;
  esac
  rm -rf "$STAGE"
  mkdir -p "$STAGE/server"
  cp -R "$BUNDLE" "$STAGE/server/maskingtool-server"
  cp "$MCPB_ROOT/manifest.macos.json" "$STAGE/manifest.json"

  echo "== 8/9 Pack MCPB and standalone ZIP ($ARCH) =="
  local MCPB_PACKAGE ZIP
  MCPB_PACKAGE="$DIST/content-masking-tool-macos-$ARCH.mcpb"
  "$MCPB" pack "$STAGE" "$MCPB_PACKAGE"

  ZIP="$DIST/maskingtool-macos-$ARCH-standalone.zip"
  rm -f "$ZIP"
  ditto -c -k --sequesterRsrc --keepParent "$BUNDLE" "$ZIP"

  echo "== 9/9 Generate checksums ($ARCH) =="
  local CHECKSUMS
  CHECKSUMS="$DIST/SHA256SUMS-macos-$ARCH.txt"
  shasum -a 256 "$MCPB_PACKAGE" "$ZIP" > "$CHECKSUMS"
  cat "$CHECKSUMS"

  SUMMARY+=(
    "  [$ARCH] Local app folder : $BUNDLE"
    "  [$ARCH] Standalone ZIP   : $ZIP"
    "  [$ARCH] Claude extension : $MCPB_PACKAGE"
    "  [$ARCH] Checksums        : $CHECKSUMS"
  )
}

for target in "${TARGETS[@]}"; do
  build_one "$target"
done

echo
echo "Done (${TARGETS[*]}):"
printf '%s\n' "${SUMMARY[@]}"
