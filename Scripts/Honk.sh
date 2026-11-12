#!/bin/bash
set -euo pipefail

SOURCE_DIR=${1:?pass the destination package directory}
WORKSPACE=${GITHUB_WORKSPACE:?GITHUB_WORKSPACE is required}
python3 "$WORKSPACE/Scripts/ReleaseSource.py" checkout honk "$SOURCE_DIR"

# Honk must not reclaim the datapath owned by an active DAE/DAED instance.
COEXISTENCE_PATCH=$WORKSPACE/Patches/honk/010-shared-datapath-ownership.patch
patch -d "$SOURCE_DIR" -p1 --batch --forward --fuzz=0 --no-backup-if-mismatch < "$COEXISTENCE_PATCH"

# Upstream checks matched core/UI refs, immutable asset tags and real hashes.
# OpenWrt verifies the archive bytes again during package download.
bash "$SOURCE_DIR/scripts/check.sh"

{
	cat "$SOURCE_DIR/ci/RELEASE-SOURCE.txt"
	cat "$SOURCE_DIR/ci/pins.env"
	printf 'HONK_MAKEFILE_SHA256=%s\n' "$(sha256sum "$SOURCE_DIR/honk/Makefile" | cut -d ' ' -f 1)"
	printf 'LUCI_HONK_MAKEFILE_SHA256=%s\n' "$(sha256sum "$SOURCE_DIR/luci-app-honk/Makefile" | cut -d ' ' -f 1)"
	printf 'HONK_LIFECYCLE_SHA256=%s\n' "$(sha256sum "$SOURCE_DIR/honk/files/lifecycle.sh" | cut -d ' ' -f 1)"
	printf 'HONK_COEXISTENCE_PATCH_SHA256=%s\n' "$(sha256sum "$COEXISTENCE_PATCH" | cut -d ' ' -f 1)"
	sed -n '/^HONK_SOURCE_TAG?=/p; /^HONK_HASH_AARCH64?=/p' "$SOURCE_DIR/honk/Makefile"
	sed -n 's/^PKG_HASH:=/DOONA_SHA256=/p' "$SOURCE_DIR/luci-app-honk/Makefile"
} > "$SOURCE_DIR/ci/HONK-SOURCE.txt"
cat "$SOURCE_DIR/ci/HONK-SOURCE.txt"
