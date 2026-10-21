#!/bin/bash
set -euo pipefail

PACKAGE_DIR=${1:-./feeds/packages/net/miniupnpd}
SCRIPT_DIR=$(cd -- "$(dirname -- "$0")" && pwd)

# Keep feed-provided services, firewall integration and compatibility fixes.
install -m 644 "$SCRIPT_DIR/../Config/miniupnpd-source.mk" "$PACKAGE_DIR/ci-source.mk"
sed -i '/^include \.\/ci-source\.mk$/d
/^include $(INCLUDE_DIR)\/package\.mk$/i include ./ci-source.mk
' "$PACKAGE_DIR/Makefile"
if ! grep -Fxq 'include ./ci-source.mk' "$PACKAGE_DIR/Makefile"; then
	echo '::error::miniupnpd source override could not be included in the feed Makefile' >&2
	exit 1
fi
cat "$PACKAGE_DIR/ci-source.mk"
