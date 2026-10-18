"""Exercise the actual CI wireless transformation against WRT_SOURCE_CHECK."""

import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_compatibility import REPO, SOURCE, WIRELESS_FILE, copy_file, run_bash


OLD_SECURITY = "${defaults?.encryption || 'psk2+ccmp'}"
NEW_SECURITY = "${band_name == '6g' ? 'sae' : (defaults?.encryption || 'psk2+ccmp')}"
LEGACY_FILE = Path("target/linux/qualcommax/base-files/etc/uci-defaults/99-set-wireless.sh")


class WirelessSettingsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        copy_file(SOURCE / WIRELESS_FILE, self.root / WIRELESS_FILE)
        self.original = (self.root / WIRELESS_FILE).read_text(encoding="utf-8")

    def apply_settings(self, **variables):
        settings = (REPO / "Scripts/Settings.sh").read_text(encoding="utf-8")
        start = settings.index("WIFI_UC=")
        wireless_step = settings[start:settings.index("CFG_FILE=")]
        run_bash(wireless_step, self.root, {
            "WRT_SSID": "CR1000A-test", "WRT_WORD": "test-password", "WRT_COUNTRY": "US",
            "GITHUB_WORKSPACE": REPO.as_posix(),
            **variables,
        })
        return (self.root / WIRELESS_FILE).read_text(encoding="utf-8")

    def test_only_requested_wireless_defaults_change(self):
        self.assertIn(OLD_SECURITY, self.original)
        expected = self.original.replace(OLD_SECURITY, NEW_SECURITY)
        expected = re.sub(r"ssid='.*'",
                          "ssid='${band_name == '6g' ? 'CR1000A-test-6G' : 'CR1000A-test'}'", expected)
        expected = re.sub(r"key='.*'", "key='test-password'", expected)
        expected = re.sub(r"country='.*'", "country='US'", expected)
        self.assertEqual(expected, self.apply_settings())

    def test_legacy_wireless_file_does_not_bypass_ucode_settings(self):
        legacy = self.root / LEGACY_FILE
        legacy.parent.mkdir(parents=True)
        legacy.write_text("BASE_SSID='legacy'\nBASE_WORD='unchanged'\n", encoding="utf-8")
        original = legacy.read_bytes()
        actual = self.apply_settings()
        self.assertIn(NEW_SECURITY, actual)
        self.assertIn("'CR1000A-test-6G' : 'CR1000A-test'", actual)
        self.assertEqual(original, legacy.read_bytes())

    def test_missing_upstream_security_field_fails(self):
        path = self.root / WIRELESS_FILE
        changed = re.sub(r"^set \$\{si\}\.encryption=.*\n", "", self.original, flags=re.MULTILINE)
        self.assertNotEqual(self.original, changed)
        path.write_text(changed, encoding="utf-8")
        with self.assertRaises(subprocess.CalledProcessError):
            self.apply_settings()
        self.assertEqual(changed, path.read_text(encoding="utf-8"))

    def test_invalid_country_is_rejected_without_modifying_source(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.apply_settings(WRT_COUNTRY="US'; invalid")
        self.assertEqual(self.original, (self.root / WIRELESS_FILE).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
