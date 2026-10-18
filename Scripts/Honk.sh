#!/bin/bash
set -euo pipefail

SOURCE_DIR=${1:?pass the destination package directory}
HONK_REPO=https://github.com/kenzok8/openwrt-honk.git
HONK_COMMIT=b733aadc69b0d3c618104241972f483adda97aed
ASSET_RELEASE=source-39098804282
ASSET_URL=https://github.com/kenzok8/openwrt-honk/releases/download/$ASSET_RELEASE

fetch_metadata() {
	local relative=$1 expected_hash=$2
	local destination="$SOURCE_DIR/$relative"
	curl --fail --location --output "$destination" "$ASSET_URL/${relative##*/}"
	printf '%s  %s\n' "$expected_hash" "$destination" | sha256sum --check
}

git init "$SOURCE_DIR"
git -C "$SOURCE_DIR" fetch --depth=1 "$HONK_REPO" "$HONK_COMMIT"
git -C "$SOURCE_DIR" -c core.autocrlf=false checkout --detach FETCH_HEAD
test "$(git -C "$SOURCE_DIR" rev-parse HEAD)" = "$HONK_COMMIT"

# These upstream includes pin the core/UI downloads and their SHA256 hashes.
# Never use the repository's floating staging URL or SKIP hash defaults.
fetch_metadata honk/generated-stage.mk 1394360edc1e12b409d1a92aea70bb7c503c9d589839fa448be2ea89d352abc1
fetch_metadata luci-app-honk/generated-doona-stage.mk 864eaeaf62a5ba251e96516103319cf7a9bf71b47b4d254a817ed571e142a9e3
fetch_metadata honk/generated-provenance.json 53c13ed198fab0b1ca7c071c5ff90673547183d696a60733e58fbc682b4ef0df

{
	printf 'PACKAGING_REPO=%s\nPACKAGING_COMMIT=%s\nASSET_RELEASE=%s\n' \
		"$HONK_REPO" "$HONK_COMMIT" "$ASSET_RELEASE"
	cat "$SOURCE_DIR/ci/pins.env"
} > "$SOURCE_DIR/ci/HONK-SOURCE.txt"
cat "$SOURCE_DIR/ci/HONK-SOURCE.txt"
