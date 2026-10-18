#!/bin/bash
set -euo pipefail

SOURCE_DIR=${1:?pass the destination package directory}
WORKSPACE=${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}
DAEDE_REPO=https://github.com/kenzok8/openwrt-daede.git
DAEDE_COMMIT=0b0e5d671e5748a060fbd79abc2f73733b09f902

git init "$SOURCE_DIR"
git -C "$SOURCE_DIR" fetch --depth=1 "$DAEDE_REPO" "$DAEDE_COMMIT"
git -C "$SOURCE_DIR" -c core.autocrlf=false checkout --detach FETCH_HEAD
test "$(git -C "$SOURCE_DIR" rev-parse HEAD)" = "$DAEDE_COMMIT"
patch --batch --fuzz=0 -p1 -d "$SOURCE_DIR" < "$WORKSPACE/Patches/daede/010-unified-backends.patch"
patch --batch --fuzz=0 -p1 -d "$SOURCE_DIR" < "$WORKSPACE/Patches/daede/020-honk-coexistence.patch"
install -m 0755 "$WORKSPACE/files/etc/uci-defaults/89-daede-migrate" \
  "$SOURCE_DIR/luci-app-daede/root/etc/uci-defaults/89-daede-migrate"

# Ship the exact packaging and component refs with each firmware release.
{
  printf 'PACKAGING_REPO=%s\nPACKAGING_COMMIT=%s\n' "$DAEDE_REPO" "$DAEDE_COMMIT"
  cat "$SOURCE_DIR/ci/pins.env"
} > "$SOURCE_DIR/ci/DAEDE-SOURCE.txt"
cat "$SOURCE_DIR/ci/DAEDE-SOURCE.txt"
