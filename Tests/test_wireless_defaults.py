"""Exercise CI settings against real owrt inputs without touching a router."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_compatibility import REPO, SOURCE, WIRELESS_FILE, copy_file, run_bash


BOARD_API = Path("package/base-files/files/lib/functions/uci-defaults.sh")
DEFAULTS = Path("files/etc/board.d/99-cr1000a-wireless-defaults")
SETTINGS_COMMAND = """
set -e
python3() { "$TEST_PYTHON" "$@"; }
. "$GITHUB_WORKSPACE/Scripts/Settings.sh"
"""


class WirelessSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for path in (WIRELESS_FILE, BOARD_API,
                     Path("package/base-files/files/bin/config_generate")):
            copy_file(SOURCE / path, self.root / path)
        self.original = (self.root / WIRELESS_FILE).read_bytes()
        for directory in ("collections", "modules/luci-mod-system", "modules/luci-mod-status"):
            (self.root / "feeds/luci" / directory).mkdir(parents=True)

    def apply_settings(self, **variables):
        run_bash(SETTINGS_COMMAND, self.root, {
            "GITHUB_WORKSPACE": REPO.as_posix(), "TEST_PYTHON": Path(sys.executable).as_posix(),
            "WRT_SSID": "CR1000A-test", "WRT_WORD": "test-password", "WRT_COUNTRY": "US",
            "WRT_CONFIG": "CR1000A-WIFI-YES", "WRT_THEME": "vantage",
            "WRT_IP": "192.168.10.1", "WRT_NAME": "CR1000A-test",
            "GITHUB_ENV": (self.root / "github-env").as_posix(),
            **variables,
        })

    def board_calls(self, board="verizon,cr1000a"):
        # Capture calls at the OpenWrt board API boundary; no actual UCI or device I/O.
        hook = (self.root / DEFAULTS).read_text(encoding="utf-8")
        upstream_import = ". /lib/functions/uci-defaults.sh\n"
        self.assertIn(upstream_import, hook)
        api = """
set -e
board_name() { printf '%s' "$TEST_BOARD"; }
board_config_update() { printf 'update\\0'; }
ucidef_set_country() { printf 'country\\0%s\\0' "$@"; }
ucidef_set_wireless() { printf 'wireless\\0'; printf '%s\\0' "$@"; }
board_config_flush() { printf 'flush\\0'; }
"""
        return run_bash(api + hook.replace(upstream_import, ""), self.root,
                        {"TEST_BOARD": board}).split("\0")[:-1]

    def test_yes_installs_native_defaults_without_rewriting_generator(self):
        try:
            self.apply_settings()
        except subprocess.CalledProcessError as error:
            self.fail(error.stdout + error.stderr)
        self.assertEqual(self.original, (self.root / WIRELESS_FILE).read_bytes())
        self.assertEqual(self.board_calls(), [
            "update", "country", "US",
            "wireless", "all", "CR1000A-test", "psk2+ccmp", "test-password",
            "wireless", "6g", "CR1000A-test-6G", "sae", "test-password", "flush",
        ])
        self.assertEqual(self.board_calls("other,router"), [])
        self.assertFalse((self.root / "files/etc/config/wireless").exists())

    def test_no_does_not_install_defaults_or_read_wireless_inputs(self):
        self.apply_settings(WRT_CONFIG="CR1000A-WIFI-NO", WRT_COUNTRY="")
        self.assertFalse((self.root / DEFAULTS).exists())
        self.assertEqual(self.original, (self.root / WIRELESS_FILE).read_bytes())

    def test_shell_metacharacters_are_literal(self):
        ssid = "test'$(printf unexpected)&"
        password = "safe'$(printf unexpected)\\value"
        self.apply_settings(WRT_SSID=ssid, WRT_WORD=password)
        self.assertEqual(self.board_calls()[4:12], [
            "all", ssid, "psk2+ccmp", password, "wireless", "6g", ssid + "-6G", "sae",
        ])
        self.assertEqual(self.board_calls()[-2], password)

    def test_invalid_country_leaves_no_generated_defaults(self):
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.apply_settings(WRT_COUNTRY="US'; invalid")
        self.assertIn("WRT_COUNTRY", failure.exception.stdout + failure.exception.stderr)
        self.assertFalse((self.root / DEFAULTS).exists())

    def test_missing_upstream_board_api_leaves_no_generated_defaults(self):
        path = self.root / BOARD_API
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace("ucidef_set_wireless()", "renamed_fn()"),
                        encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError) as failure:
            self.apply_settings()
        self.assertIn("ucidef_set_wireless", failure.exception.stderr)
        self.assertFalse((self.root / DEFAULTS).exists())


if __name__ == "__main__":
    unittest.main()
