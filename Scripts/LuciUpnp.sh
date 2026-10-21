#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
PACKAGE_DIR=$(cd -- "${1:-./feeds/luci/applications/luci-app-upnp}" && pwd -P)
PATCH_FILE="$SCRIPT_DIR/../Patches/luci-app-upnp/001-upstream-nft-counter.patch"
READER="$PACKAGE_DIR/root/usr/share/rpcd/ucode/luci.upnp"
UPSTREAM_COMMIT=9f52246f6fc40420be8ee962502ac967f0f3ec26

# Apply the reviewed upstream change only; do not replace a newer feed package.
if patch --dry-run --batch --forward --fuzz=0 -p3 -d "$PACKAGE_DIR" < "$PATCH_FILE" >/dev/null; then
	patch --batch --forward --fuzz=0 --no-backup-if-mismatch -p3 -d "$PACKAGE_DIR" < "$PATCH_FILE"
	MODE=upstream-pr-backport
elif patch --dry-run --batch --force --reverse --fuzz=0 -p3 -d "$PACKAGE_DIR" < "$PATCH_FILE" >/dev/null; then
	MODE=native-feed
else
	echo '::error::LuCI UPnP reader changed; review upstream parsing before adapting this backport' >&2
	exit 1
fi

{
	printf 'mode=%s\nupstream_pr=https://github.com/openwrt/luci/pull/9148\n' "$MODE"
	printf 'upstream_commit=%s\nrpc_sha256=%s\n' "$UPSTREAM_COMMIT" "$(sha256sum "$READER" | cut -d ' ' -f 1)"
} > "$PACKAGE_DIR/ci-luci-upnp-source.txt"
cat "$PACKAGE_DIR/ci-luci-upnp-source.txt"
