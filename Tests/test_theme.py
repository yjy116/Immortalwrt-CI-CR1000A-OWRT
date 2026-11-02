"""Exercise theme selection against the actual Settings.sh configuration step."""

from pathlib import Path
import tempfile
import unittest

import yaml

from test_compatibility import REPO, run_bash


def theme_config(theme):
    settings = (REPO / "Scripts/Settings.sh").read_text(encoding="utf-8")
    start = settings.index('echo "CONFIG_PACKAGE_luci=y"')
    end = settings.index('if [ -f "$GITHUB_WORKSPACE/Config/PRIVATE.txt" ]')
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        run_bash(settings[start:end], root, {"WRT_THEME": theme})
        return set((root / ".config").read_text(encoding="utf-8").splitlines())


class ThemeTests(unittest.TestCase):
    def test_vantage_uses_the_real_dashboard_package(self):
        config = theme_config("vantage")
        self.assertIn("CONFIG_PACKAGE_luci-theme-vantage=y", config)
        self.assertIn("CONFIG_PACKAGE_luci-app-vantage=y", config)
        self.assertNotIn("CONFIG_PACKAGE_luci-app-vantage-config=y", config)

    def test_aurora_companion_remains_available(self):
        config = theme_config("aurora")
        self.assertIn("CONFIG_PACKAGE_luci-theme-aurora=y", config)
        self.assertIn("CONFIG_PACKAGE_luci-app-aurora-config=y", config)

    def test_production_and_test_use_vantage_for_both_variants(self):
        for name in ("CR1000A.yml", "CR1000A-TEST.yml"):
            with self.subTest(workflow=name):
                path = REPO / ".github/workflows" / name
                job = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["config"]
                self.assertEqual("vantage", job["with"]["WRT_THEME"])
                self.assertEqual(["CR1000A-WIFI-YES", "CR1000A-WIFI-NO"],
                                 job["strategy"]["matrix"]["CONFIG"])


if __name__ == "__main__":
    unittest.main()
