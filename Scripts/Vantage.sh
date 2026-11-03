#!/bin/bash
set -euo pipefail

SOURCE=${1:?pass the Vantage package repository}
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PATCH="$ROOT/Patches/vantage/010-software-bridge-fdb.patch"
MODULES="$SOURCE/luci-app-vantage/root/usr/share/ucode"

# Fail visibly on upstream drift instead of silently shipping the slow collector.
patch --batch --forward --fuzz=0 --dry-run -p1 -d "$SOURCE" < "$PATCH"
patch --batch --forward --fuzz=0 --no-backup-if-mismatch -p1 -d "$SOURCE" < "$PATCH"
install -Dm644 "$ROOT/Patches/vantage/vantage_bridge.uc" "$MODULES/vantage_bridge.uc"
echo 'Vantage wired collector: software bridge FDB; no hardware FDB dump'
