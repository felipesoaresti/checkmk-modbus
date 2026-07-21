#!/usr/bin/env bash
# Rebuilds the modbus-<version>.mkp package from src/ + info + info.json.
#
# Reproduces the exact archive layout Checkmk's own `cmk-mkp-tool` produces
# (confirmed by inspecting the original modbus-1.0.2.mkp byte-for-byte):
#   outer archive: gzip'ed PAX tar containing, in this order, the files
#                  `info` (Python repr manifest), `info.json` (same manifest
#                  as JSON) and `cmk_addons_plugins.tar` (mode 0644, owner
#                  root:root)
#   inner archive: plain (non-gzipped) PAX tar of the actual plugin files
#                  under `modbus/...`, mode 0700, owner cmk:cmk (uid 996,
#                  gid 1001 on the system the original package was built on)
#
# If a real Checkmk 2.4 site is available, prefer using its own `mkp`/
# `cmk-mkp-tool` to build+validate the package instead of this script.
#
# Usage: ./build.sh [version]   (default: reads version from info.json)

set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

VERSION="${1:-$(python3 -c "import json; print(json.load(open('info.json'))['version'])")}"
OUT="modbus-${VERSION}.mkp"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Building ${OUT} from src/ (version ${VERSION})"

# 1. Inner tar: the actual plugin files, as they get installed under
#    local/lib/python3/cmk_addons/plugins/. Add files explicitly (no
#    directory entries) to match the layout cmk-mkp-tool produces.
cp -a src/modbus "$WORK/modbus"
find "$WORK/modbus" -name "__pycache__" -type d -exec rm -rf {} +
find "$WORK/modbus" -type f -exec chmod 700 {} \;
FILES=$(cd "$WORK" && find modbus -type f | sort)
tar --format=pax --owner=cmk:996 --group=cmk:1001 -C "$WORK" -cf "$WORK/cmk_addons_plugins.tar" $FILES

# 2. Outer tar+gzip: info, info.json, cmk_addons_plugins.tar (root:root, 0644).
cp info "$WORK/info"
cp info.json "$WORK/info.json"
chmod 644 "$WORK/info" "$WORK/info.json" "$WORK/cmk_addons_plugins.tar"
tar --format=pax --owner=root:0 --group=root:0 -C "$WORK" -czf "$OUT" info info.json cmk_addons_plugins.tar

echo "Done: $(pwd)/${OUT}"
tar -tzvf "$OUT"
