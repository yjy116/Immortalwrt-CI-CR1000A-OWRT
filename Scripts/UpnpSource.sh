#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail

PACKAGE_ROOT=$(cd -- "${1:?Expected VIKINGYFY packages directory}" && pwd -P)
OUTPUT=${2:?Expected provenance output directory}
PROVIDER_COMMIT=$(git -C "$PACKAGE_ROOT" rev-parse HEAD)

make_value() {
	local value
	value=$(awk -v key="$2" 'index($0, key ":=") == 1 {
		sub(/^[^:]+:=/, ""); sub(/\r$/, ""); print; exit
	}' "$1")
	[[ -n "$value" ]] || { echo "::error::Missing $2 in $1" >&2; return 1; }
	printf '%s' "$value"
}

file_hash() {
	sha256sum "$1" | cut -d ' ' -f 1
}

CORE="$PACKAGE_ROOT/miniupnpd/Makefile"
LUCI="$PACKAGE_ROOT/luci-app-upnp/Makefile"
RPC="$PACKAGE_ROOT/luci-app-upnp/root/usr/share/rpcd/ucode/luci.upnp"
CORE_VERSION=$(make_value "$CORE" PKG_VERSION)
CORE_RELEASE=$(make_value "$CORE" PKG_RELEASE)
SOURCE_COMMIT=$(make_value "$CORE" PKG_SOURCE_VERSION)
SOURCE_HASH=$(make_value "$CORE" PKG_HASH)
LUCI_VERSION=$(make_value "$LUCI" PKG_VERSION)
LUCI_RELEASE=$(make_value "$LUCI" PKG_RELEASE)
CORE_HASH=$(file_hash "$CORE")
LUCI_HASH=$(file_hash "$LUCI")
RPC_HASH=$(file_hash "$RPC")

# Record the upstream pair without rewriting its recipes or runtime files.
mkdir -p "$OUTPUT"
{
	printf 'mode=upstream-pair\nprovider=VIKINGYFY/packages\nprovider_commit=%s\n' "$PROVIDER_COMMIT"
	printf 'version=%s-r%s\nsource_commit=%s\nsource_sha256=%s\n' \
		"$CORE_VERSION" "$CORE_RELEASE" "$SOURCE_COMMIT" "$SOURCE_HASH"
	printf 'makefile_sha256=%s\n' "$CORE_HASH"
} > "$OUTPUT/MINIUPNPD-SOURCE.txt"
{
	printf 'mode=upstream-pair\nprovider=VIKINGYFY/packages\nprovider_commit=%s\n' "$PROVIDER_COMMIT"
	printf 'version=%s-r%s\nmakefile_sha256=%s\nrpc_sha256=%s\n' \
		"$LUCI_VERSION" "$LUCI_RELEASE" "$LUCI_HASH" "$RPC_HASH"
} > "$OUTPUT/LUCI-UPNP-SOURCE.txt"
cat "$OUTPUT/MINIUPNPD-SOURCE.txt" "$OUTPUT/LUCI-UPNP-SOURCE.txt"
