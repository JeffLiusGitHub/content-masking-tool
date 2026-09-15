#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DIST="$ROOT/dist"

ARCH="${1:-}"
TEST_MODE="${2:-}"
case "$ARCH" in
  arm64|x86_64) ;;
  *) echo "ERROR: first argument must be arm64 or x86_64." >&2; exit 1 ;;
esac
if [[ "$TEST_MODE" != "--test-only" ]]; then
  echo "ERROR: formal PKG creation is disabled until production identity and signing are configured." >&2
  echo "       Use --test-only for a clearly labelled unsigned package." >&2
  exit 1
fi

PYTHON="$ROOT/.build-venv-$ARCH/bin/python"
PAYLOAD="$DIST/pyinstaller-macos-$ARCH/maskingtool-server"
[[ -x "$PYTHON" ]] || { echo "ERROR: build Python not found: $PYTHON" >&2; exit 1; }
[[ -x "$PAYLOAD/maskingtool-server" ]] || { echo "ERROR: frozen executable missing." >&2; exit 1; }
[[ -d "$PAYLOAD/_internal" ]] || { echo "ERROR: frozen payload is missing _internal." >&2; exit 1; }

VERSION="$(cd "$ROOT" && "$PYTHON" -c 'import tomllib, pathlib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')"

ARCH_ID="${ARCH/_/-}"
PACKAGE_ID="org.contentmaskingtool.unsigned-test-only.$ARCH_ID"
STAGE="$DIST/pkg-stage-$ARCH"
PKG="$DIST/content-masking-tool-macos-$ARCH-$VERSION-unsigned-test-only.pkg"
METADATA="$DIST/content-masking-tool-macos-$ARCH-$VERSION-unsigned-test-only.json"

case "$STAGE" in
  "$DIST"/pkg-stage-arm64|"$DIST"/pkg-stage-x86_64) ;;
  *) echo "ERROR: unsafe package staging path: $STAGE" >&2; exit 1 ;;
esac
/bin/rm -rf "$STAGE"
/bin/mkdir -p \
  "$STAGE/Library/Application Support/ContentMaskingTool" \
  "$STAGE/usr/local/bin"
/usr/bin/ditto "$PAYLOAD" \
  "$STAGE/Library/Application Support/ContentMaskingTool/maskingtool-server"
/bin/cp "$SCRIPT_DIR/launcher.sh" "$STAGE/usr/local/bin/maskingtool-server"
/usr/bin/sed "s|@@PACKAGE_ID@@|$PACKAGE_ID|g" "$SCRIPT_DIR/uninstall.sh.in" > \
  "$STAGE/Library/Application Support/ContentMaskingTool/uninstall.sh"
/bin/chmod 0755 \
  "$STAGE/usr/local/bin/maskingtool-server" \
  "$STAGE/Library/Application Support/ContentMaskingTool/uninstall.sh" \
  "$STAGE/Library/Application Support/ContentMaskingTool/maskingtool-server/maskingtool-server"

/usr/bin/pkgbuild \
  --root "$STAGE" \
  --identifier "$PACKAGE_ID" \
  --version "$VERSION" \
  --install-location / \
  --ownership recommended \
  "$PKG"

PAYLOAD_COUNT="$(/usr/sbin/pkgutil --payload-files "$PKG" | /usr/bin/wc -l | /usr/bin/tr -d ' ')"
"$PYTHON" "$SCRIPT_DIR/generate_pkg_metadata.py" \
  --output "$METADATA" \
  --version "$VERSION" \
  --architecture "$ARCH" \
  --package-id "$PACKAGE_ID" \
  --payload-file-count "$PAYLOAD_COUNT"

echo "Unsigned test PKG: $PKG"
echo "Metadata         : $METADATA"
