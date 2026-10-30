#!/bin/bash
# SPDX-License-Identifier: MIT
set -euo pipefail

KIND=${1:?Expected config or manifest}
INPUT=${2:?Expected input file}
: "${WRT_CONFIG:?}"

fail() {
	echo "::error::$*"
	exit 1
}

[[ -s "$INPUT" ]] || fail "Missing or empty $KIND: $INPUT"
case "$KIND" in config|manifest) ;; *) fail "Unknown check: $KIND" ;; esac
case "$WRT_CONFIG" in
	CR1000A-WIFI-YES) WIFI=yes ;;
	CR1000A-WIFI-NO) WIFI=no ;;
	*) fail "Unknown CR1000A profile: $WRT_CONFIG" ;;
esac

REQUIRED=(kmod-dsa-rtl9303-spi cr1000a-recovery kmod-nss-wifi-drv
	nss-firmware luci-app-qca-ppe-qos qca-ppe-qos)
RADIOS=(kmod-ath11k kmod-ath11k-ahb kmod-ath11k-pci)

has_package() {
	if [[ "$KIND" == config ]]; then
		grep -Eq "^CONFIG_PACKAGE_${1}=${2}$" "$INPUT"
	else
		grep -Eq "^${1} - [^[:space:]]+" "$INPUT"
	fi
}

for PACKAGE in "${REQUIRED[@]}"; do
	has_package "$PACKAGE" y || fail "$KIND is missing required owrt package: $PACKAGE"
done

for PACKAGE in "${RADIOS[@]}"; do
	if [[ "$WIFI" == yes ]]; then
		has_package "$PACKAGE" '(y|m)' || fail "$KIND is missing WiFi-YES package: $PACKAGE"
	elif has_package "$PACKAGE" '(y|m)'; then
		fail "$KIND enables $PACKAGE in WiFi-NO"
	fi
done

if [[ "$KIND" == config ]]; then
	if [[ "$WIFI" == yes ]]; then
		grep -qx 'CONFIG_ATH11K_NSS_WIFI=y' "$INPUT" || fail 'WiFi-YES lacks ATH11K_NSS_WIFI'
	elif grep -Eq '^CONFIG_ATH11K_NSS_WIFI=(y|m)$' "$INPUT"; then
		fail 'WiFi-NO enables ATH11K_NSS_WIFI'
	fi
fi

echo "Verified $WRT_CONFIG $KIND: native PPE/NSS and PPE QoS packages"
