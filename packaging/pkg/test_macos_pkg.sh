#!/usr/bin/env bash
set -euo pipefail

PKG="${1:-}"
METADATA="${2:-}"
[[ -f "$PKG" ]] || { echo "ERROR: PKG not found: $PKG" >&2; exit 1; }
[[ -f "$METADATA" ]] || { echo "ERROR: metadata not found: $METADATA" >&2; exit 1; }
case "$PKG" in
  *-unsigned-test-only.pkg) ;;
  *) echo "ERROR: refusing package without unsigned-test-only label." >&2; exit 1 ;;
esac

PYTHON="$(command -v python3)"
VERSION="$($PYTHON -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' "$METADATA")"
ARCH="$($PYTHON -c 'import json,sys; print(json.load(open(sys.argv[1]))["architecture"])' "$METADATA")"
PACKAGE_ID="$($PYTHON -c 'import json,sys; print(json.load(open(sys.argv[1]))["packageIdentifier"])' "$METADATA")"
SERVER_ROOT='/Library/Application Support/ContentMaskingTool/maskingtool-server'
LAUNCHER='/usr/local/bin/maskingtool-server'
UNINSTALLER='/Library/Application Support/ContentMaskingTool/uninstall.sh'
SENTINEL_DIR="$HOME/Library/Application Support/ContentMaskingTool"
SENTINEL="$SENTINEL_DIR/installer-data-retention-sentinel-$$.txt"

cleanup() {
  if [[ -x "$UNINSTALLER" ]]; then
    sudo "$UNINSTALLER" >/dev/null 2>&1 || true
  fi
  /bin/rm -f "$SENTINEL"
}
trap cleanup EXIT

/bin/mkdir -p "$SENTINEL_DIR"
echo preserve > "$SENTINEL"
sudo /usr/sbin/installer -pkg "$PKG" -target /

[[ -d "$SERVER_ROOT/_internal" ]] || { echo "ERROR: installed _internal missing." >&2; exit 1; }
[[ -x "$LAUNCHER" ]] || { echo "ERROR: launcher missing or not executable." >&2; exit 1; }
[[ -x "$UNINSTALLER" ]] || { echo "ERROR: uninstall helper missing." >&2; exit 1; }

PROBE="$($LAUNCHER --version)"
[[ "$PROBE" == "maskingtool-server $VERSION" ]] || {
  echo "ERROR: version probe mismatch: $PROBE" >&2
  exit 1
}
/usr/sbin/pkgutil --pkg-info "$PACKAGE_ID" | /usr/bin/grep -F "version: $VERSION"
/usr/bin/file "$SERVER_ROOT/maskingtool-server" | /usr/bin/grep -F "$ARCH"

for installed_path in "$SERVER_ROOT" "$LAUNCHER" "$UNINSTALLER"; do
  OWNER_MODE="$(/usr/bin/stat -f '%Su:%Sg %Lp' "$installed_path")"
  case "$OWNER_MODE" in
    root:wheel\ *) ;;
    *) echo "ERROR: unexpected owner for $installed_path: $OWNER_MODE" >&2; exit 1 ;;
  esac
done

# Repeat installation must be idempotent for the same package/version.
sudo /usr/sbin/installer -pkg "$PKG" -target /
sudo "$UNINSTALLER"

[[ ! -e "$SERVER_ROOT" ]] || { echo "ERROR: server root remains after uninstall." >&2; exit 1; }
[[ ! -e "$LAUNCHER" ]] || { echo "ERROR: launcher remains after uninstall." >&2; exit 1; }
if /usr/sbin/pkgutil --pkg-info "$PACKAGE_ID" >/dev/null 2>&1; then
  echo "ERROR: package receipt remains after uninstall." >&2
  exit 1
fi
[[ -f "$SENTINEL" ]] || { echo "ERROR: per-user data sentinel was removed." >&2; exit 1; }

trap - EXIT
/bin/rm -f "$SENTINEL"
echo "PKG lifecycle smoke test passed ($ARCH)"
