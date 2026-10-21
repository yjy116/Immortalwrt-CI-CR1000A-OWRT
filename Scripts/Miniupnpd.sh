#!/bin/bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
PACKAGE_DIR=$(cd -- "${1:-./feeds/packages/net/miniupnpd}" && pwd -P)
SOURCE_CONFIG="$SCRIPT_DIR/../Config/miniupnpd-source.mk"
FIX_VERSION=$(sed -n 's/^PKG_VERSION:=//p' "$SOURCE_CONFIG")
FIX_COMMIT=$(sed -n 's/^PKG_SOURCE_VERSION:=//p' "$SOURCE_CONFIG")
PACKAGING_COMMIT=72c7391fb2d04080afd0bfe919605749f81eb747
PACKAGING_HASH=69bac8ac5ec603a31d2b4ce265dade7b1f43ef4fc8f2caeaf3ab6fb310339c2c

fail() {
	echo "::error::$*" >&2
	exit 1
}

cleanup() {
	if [[ -d "$WORK/previous" && ! -d "$PACKAGE_DIR" ]]; then
		echo "::error::original miniupnpd package retained at $WORK/previous" >&2
		return
	fi
	rm -rf -- "$WORK"
}

use_native_feed() {
	local tag="miniupnpd_${FEED_VERSION//./_}" merge_base
	grep -Eq '^PKG_SOURCE_URL:=https://github.com/miniupnp/miniupnp/releases/download/' \
		"$PACKAGE_DIR/Makefile" || fail 'miniupnpd feed no longer uses an official release URL; review its source'
	merge_base=$(gh api "repos/miniupnp/miniupnp/compare/$FIX_COMMIT...$tag" --jq '.merge_base_commit.sha')
	[[ "$merge_base" == "$FIX_COMMIT" ]] || fail "miniupnpd $FEED_VERSION does not contain official fix $FIX_COMMIT"
	printf 'mode=native-feed\nversion=%s\nrelease_tag=%s\nverified_fix=%s\n' \
		"$FEED_VERSION" "$tag" "$FIX_COMMIT" > "$PACKAGE_DIR/ci-source.txt"
}

prepare_fixed_package() {
	local archive=${MINIUPNPD_PACKAGING_ARCHIVE:-$WORK/packages.tar.gz}
	if [[ -z "${MINIUPNPD_PACKAGING_ARCHIVE:-}" ]]; then
		curl --fail --location --silent --show-error \
			"https://codeload.github.com/immortalwrt/packages/tar.gz/$PACKAGING_COMMIT" -o "$archive"
	fi
	[[ "$(sha256sum "$archive" | cut -d ' ' -f 1)" == "$PACKAGING_HASH" ]] || fail 'miniupnpd packaging checksum mismatch'
	mkdir "$WORK/package"
	gzip -dc "$archive" | tar -xf - -C "$WORK/package" --strip-components 3 \
		"packages-$PACKAGING_COMMIT/net/miniupnpd"
	install -m 644 "$SOURCE_CONFIG" "$WORK/package/ci-source.mk"
	sed -i '/^include $(INCLUDE_DIR)\/package\.mk$/i include ./ci-source.mk' "$WORK/package/Makefile"
	grep -Fxq 'include ./ci-source.mk' "$WORK/package/Makefile" || fail 'miniupnpd source override was not included'
	{
		printf 'mode=official-fix\npackaging_commit=%s\npackaging_sha256=%s\n' "$PACKAGING_COMMIT" "$PACKAGING_HASH"
		cat "$SOURCE_CONFIG"
	} > "$WORK/package/ci-source.txt"
}

FEED_VERSION=$(sed -n 's/^PKG_VERSION:=//p' "$PACKAGE_DIR/Makefile")
[[ "$FEED_VERSION" =~ ^[0-9]+(\.[0-9]+)+$ ]] || fail 'miniupnpd PKG_VERSION is missing or not a numeric release'
[[ "${PACKAGE_DIR##*/}" == miniupnpd ]] || fail 'expected a miniupnpd package directory'

if [[ "$FEED_VERSION" != "$FIX_VERSION" && \
	"$(printf '%s\n' "$FIX_VERSION" "$FEED_VERSION" | sort -V | tail -n 1)" == "$FEED_VERSION" ]]; then
	use_native_feed
else
	# Freeze the complete integration, not just the core under changing feed patches.
	WORK=$(mktemp -d "${PACKAGE_DIR%/*}/.miniupnpd-ci.XXXXXX")
	trap cleanup EXIT
	prepare_fixed_package
	mv -- "$PACKAGE_DIR" "$WORK/previous"
	if ! mv -- "$WORK/package" "$PACKAGE_DIR"; then
		mv -- "$WORK/previous" "$PACKAGE_DIR"
		fail 'miniupnpd package replacement failed; original package restored'
	fi
fi
cat "$PACKAGE_DIR/ci-source.txt"
