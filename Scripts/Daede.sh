#!/bin/bash
set -euo pipefail

SOURCE_DIR=${1:?pass the destination package directory}
WORKSPACE=${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}
python3 "$WORKSPACE/Scripts/ReleaseSource.py" checkout daede "$SOURCE_DIR"
patch --batch --forward --fuzz=0 --no-backup-if-mismatch -p1 -d "$SOURCE_DIR" < "$WORKSPACE/Patches/daede/010-unified-backends.patch"
patch --batch --forward --fuzz=0 --no-backup-if-mismatch -p1 -d "$SOURCE_DIR" < "$WORKSPACE/Patches/daede/020-honk-coexistence.patch"
install -m 0755 "$WORKSPACE/files/etc/uci-defaults/89-daede-migrate" \
  "$SOURCE_DIR/luci-app-daede/root/etc/uci-defaults/89-daede-migrate"

# Ship the exact packaging and component refs with each firmware release.
{
  cat "$SOURCE_DIR/ci/RELEASE-SOURCE.txt"
  cat "$SOURCE_DIR/ci/pins.env"
} > "$SOURCE_DIR/ci/DAEDE-SOURCE.txt"
cat "$SOURCE_DIR/ci/DAEDE-SOURCE.txt"
