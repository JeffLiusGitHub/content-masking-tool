#!/bin/sh
set -eu

exec "/Library/Application Support/ContentMaskingTool/maskingtool-server/maskingtool-server" "$@"
