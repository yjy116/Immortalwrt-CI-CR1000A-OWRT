#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PLUGIN=${1:?pass the actual luci.vantage plugin file}
WORK=$(mktemp -d)
trap 'rm -rf -- "$WORK"' EXIT HUP INT TERM
timeout 60 ucode -L "$ROOT/Tests/vantage" -L "$ROOT/Patches/vantage" \
	-D "WORK=$WORK" -D "PLUGIN=$PLUGIN" "$ROOT/Tests/vantage/test_wired.uc"
