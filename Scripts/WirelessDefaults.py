"""Install fresh wireless defaults through OpenWrt's native board.d API."""

import os
import re
from pathlib import Path
from shlex import quote


BOARD_API = Path("package/base-files/files/lib/functions/uci-defaults.sh")
BOARD_HOOK = Path("files/etc/board.d/99-cr1000a-wireless-defaults")


def check_board_api():
    source = BOARD_API.read_text(encoding="utf-8")
    for name in ("ucidef_set_country", "ucidef_set_wireless"):
        if not re.search(rf"^\s*{name}\s*\(\s*\)", source, re.MULTILINE):
            raise ValueError(f"OpenWrt board API is missing {name} in {BOARD_API}")


def install_defaults():
    country = os.environ.get("WRT_COUNTRY", "")
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError("WRT_COUNTRY must be the actual two-letter country code")
    ssid = os.environ.get("WRT_SSID", "")
    key = os.environ.get("WRT_WORD", "")
    if not ssid or not key:
        raise ValueError("WRT_SSID and WRT_WORD are required for WiFi-YES")

    check_board_api()
    hook = f"""#!/bin/sh
. /lib/functions/uci-defaults.sh

[ "$(board_name)" = verizon,cr1000a ] || exit 0

board_config_update
ucidef_set_country {quote(country)}
ucidef_set_wireless all {quote(ssid)} psk2+ccmp {quote(key)}
ucidef_set_wireless 6g {quote(ssid + "-6G")} sae {quote(key)}
board_config_flush
"""
    BOARD_HOOK.parent.mkdir(parents=True, exist_ok=True)
    BOARD_HOOK.write_text(hook, encoding="utf-8", newline="\n")
    print(f"Installed CR1000A WiFi-YES defaults via {BOARD_HOOK}")


if __name__ == "__main__":
    try:
        install_defaults()
    except (OSError, ValueError) as error:
        raise SystemExit(f"Wireless defaults: {error}") from None
