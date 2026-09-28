"""Audit against the pinned CI template and AX6600 plugin reference checkouts."""

import os
from pathlib import Path
import re
import unittest


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = Path(os.environ["WRT_CI_TEMPLATE"])
REFERENCE = Path(os.environ["WRT_PLUGIN_REFERENCE"])


def text(root, path):
    return (root / path).read_text(encoding="utf-8")


def enabled(content):
    return set(re.findall(r"^(CONFIG_[A-Za-z0-9_+.-]+)=y$", content, re.MULTILINE))


class AlignmentTests(unittest.TestCase):
    def test_general_configuration_matches_template(self):
        self.assertEqual(text(TEMPLATE, "Config/GENERAL.txt"), text(REPO, "Config/GENERAL.txt"))

    def test_only_cr1000a_is_selected_with_native_support(self):
        for mode in ("YES", "NO"):
            with self.subTest(mode=mode):
                config = enabled(text(REPO, f"Config/CR1000A-WIFI-{mode}.txt"))
                devices = {key for key in config if key.startswith("CONFIG_TARGET_DEVICE_")}
                self.assertEqual({"CONFIG_TARGET_DEVICE_qualcommax_ipq807x_DEVICE_verizon_cr1000a"}, devices)
                self.assertIn("CONFIG_PACKAGE_kmod-dsa-rtl9303-spi", config)
                self.assertIn("CONFIG_PACKAGE_cr1000a-recovery", config)
                self.assertNotIn("CONFIG_PACKAGE_cr1000a-support", config)

    def test_all_reference_general_apps_are_included(self):
        expected = enabled(text(REFERENCE, "Config/GENERAL.txt"))
        expected = {key for key in expected if key.startswith("CONFIG_PACKAGE_")
                    and not key.startswith("CONFIG_PACKAGE_kmod-")}
        expected.discard("CONFIG_PACKAGE_sqm-scripts-nss")
        expected.update({"CONFIG_PACKAGE_luci-app-sqm", "CONFIG_PACKAGE_sqm-scripts"})
        actual = enabled(text(REPO, "Config/GENERAL.txt") + text(REPO, "Config/EXTRA.txt"))
        self.assertEqual(set(), expected - actual)
        self.assertNotIn("CONFIG_PACKAGE_sqm-scripts-nss", actual)

    def test_no_legacy_hardware_injection_or_wrong_board_helpers(self):
        scripts = "\n".join(path.read_text(encoding="utf-8")
                            for path in (REPO / "Scripts").glob("*.sh"))
        workflow = text(REPO, ".github/workflows/WRT-CORE.yml")
        for obsolete in ("yjy116/files", "qcom,no-phy", "forced-speed = <10000>",
                         "08-cr1000a-no-phy-link", "athena-led", "ARM64_BRBE"):
            self.assertNotIn(obsolete, scripts + workflow)
        self.assertFalse((REPO / "Patches/qca-nss-dp/08-cr1000a-no-phy-link.patch").exists())

    def test_config_merge_and_cache_include_plugin_layer(self):
        self.assertIn("Config/EXTRA.txt", text(REPO, ".github/workflows/WRT-CORE.yml"))
        self.assertIn("Config/EXTRA.txt", text(REPO, "Scripts/CacheKey.sh"))

    def test_old_daed_and_netspeedtest_sources_are_not_reintroduced(self):
        packages = text(REPO, "Scripts/Packages.sh")
        self.assertNotIn("QiuSimons/luci-app-daed", packages)
        self.assertNotIn('UPDATE_PACKAGE "netspeedtest"', packages)
        self.assertIn("Scripts/Daede.sh", packages)
        extras = text(REPO, "Config/EXTRA.txt")
        self.assertIn("CONFIG_DAE_USE_KERNEL_BTF=y", extras)
        self.assertIn("CONFIG_DAED_USE_KERNEL_BTF=y", extras)
        self.assertIn("CONFIG_KERNEL_DEBUG_INFO_BTF=y", extras)


if __name__ == "__main__":
    unittest.main()
