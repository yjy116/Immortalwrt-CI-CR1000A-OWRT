# Official 2.3.11 + the CGNAT reconnect fix, without a local core patch.
# Paired with the immutable packaging snapshot in Scripts/Miniupnpd.sh.
# https://github.com/miniupnp/miniupnp/commit/2dcf63959950dbb2c3f97b7bd63773d499749134
PKG_VERSION:=2.3.11
PKG_RELEASE:=2
PKG_SOURCE_VERSION:=2dcf63959950dbb2c3f97b7bd63773d499749134
PKG_SOURCE_URL:=https://codeload.github.com/miniupnp/miniupnp/tar.gz/$(PKG_SOURCE_VERSION)?
PKG_SOURCE:=$(PKG_NAME)-$(PKG_VERSION)-$(PKG_SOURCE_VERSION).tar.gz
PKG_HASH:=cd32444850ae75a63d49b043baad9051ddb37080186f296eb5de97f7f70a0b3a

# The official Git archive contains several projects; build only the daemon.
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_NAME)-$(BUILD_VARIANT)/$(PKG_NAME)-$(PKG_VERSION)/miniupnpd
TAR_OPTIONS+= --strip-components 1
