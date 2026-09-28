"""Validate matrix expansion and upstream no-WiFi hardware settings."""

import os
from pathlib import Path
import tempfile
import unittest

import yaml

from test_compatibility import DTS_FILE, REPO, SOURCE, copy_file, run_bash


TEMPLATE = Path(os.environ["WRT_CI_TEMPLATE"])
PROFILES = ["CR1000A-WIFI-YES", "CR1000A-WIFI-NO"]
NOWIFI_FILE = Path("target/linux/qualcommax/files/arch/arm64/boot/dts/qcom/ipq8074-nowifi.dtsi")


def read(root, path):
    return (root / path).read_text(encoding="utf-8")


def assignments(content):
    return dict(line.split("=", 1) for line in content.splitlines()
                if line.startswith("CONFIG_") and "=" in line)


class WifiProfileTests(unittest.TestCase):
    def test_both_workflows_schedule_parallel_variants(self):
        for filename in ("CR1000A.yml", "CR1000A-TEST.yml"):
            with self.subTest(workflow=filename):
                workflow = yaml.safe_load(read(REPO, f".github/workflows/{filename}"))
                job = workflow["jobs"]["config"]
                strategy = job["strategy"]
                self.assertEqual(PROFILES, strategy["matrix"]["CONFIG"])
                self.assertEqual(["yjy116/immortalwrt"], strategy["matrix"]["SOURCE"])
                self.assertEqual(["owrt"], strategy["matrix"]["BRANCH"])
                self.assertFalse(strategy["fail-fast"])
                self.assertGreaterEqual(strategy.get("max-parallel", len(PROFILES)), len(PROFILES))
                self.assertNotIn("needs", job)
                self.assertEqual("${{matrix.CONFIG}}", job["with"]["WRT_CONFIG"])
                self.assertEqual("./.github/workflows/WRT-CORE.yml", job["uses"])

    def test_only_no_profile_adds_upstream_wireless_exclusions(self):
        expected = assignments(read(TEMPLATE, "Config/IPQ807X-WIFI-NO.txt"))
        expected = {key: value for key, value in expected.items() if value == "n"}
        self.assertIn("CONFIG_PACKAGE_kmod-ath11k-pci", expected)
        self.assertIn("CONFIG_PACKAGE_kmod-ath11k-ahb", expected)
        yes = assignments(read(REPO, f"Config/{PROFILES[0]}.txt"))
        no = assignments(read(REPO, f"Config/{PROFILES[1]}.txt"))
        self.assertTrue(set(yes).isdisjoint(expected))
        self.assertEqual({**yes, **expected}, no)
        merged = assignments("\n".join([
            read(REPO, f"Config/{PROFILES[1]}.txt"),
            read(REPO, "Config/GENERAL.txt"), read(REPO, "Config/EXTRA.txt"),
        ]))
        self.assertEqual(expected, {key: merged[key] for key in expected})

    def test_old_single_profile_is_removed(self):
        self.assertFalse((REPO / "Config/CR1000A.txt").exists())

    def test_release_tags_and_assets_keep_mode_identity(self):
        core = yaml.safe_load(read(REPO, ".github/workflows/WRT-CORE.yml"))
        steps = {step["name"]: step for step in core["jobs"]["core"]["steps"]}
        tag = steps["Release Firmware"]["with"]["tag_name"]
        self.assertTrue(tag.startswith("${{env.WRT_CONFIG}}-"))
        self.assertIn('"$WRT_WIFI"', steps["Package Firmware"]["run"])
        self.assertIn('"$WRT_CONFIG"', steps["Package Firmware"]["run"])


class WifiDtsTests(unittest.TestCase):
    def apply_mode(self, mode):
        settings = read(REPO, "Scripts/Settings.sh")
        mode_step = settings[settings.index('if [[ "${WRT_CONFIG,,}"'):]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_file(SOURCE / DTS_FILE, root / DTS_FILE)
            sentinel = DTS_FILE.parent / "ipq8074-nowifi.dtsi"
            copy_file(SOURCE / NOWIFI_FILE, root / sentinel)
            env = root / "github_env"
            env.write_text("WRT_WIFI=wifi-yes\n", encoding="utf-8")
            run_bash(mode_step, root, {
                "WRT_CONFIG": f"CR1000A-WIFI-{mode}", "WRT_TARGET": "qualcommax",
                "GITHUB_ENV": env.as_posix(),
            })
            self.assertEqual((SOURCE / NOWIFI_FILE).read_bytes(), (root / sentinel).read_bytes())
            return read(root, DTS_FILE), env.read_text(encoding="utf-8").splitlines()[-1]

    def test_yes_keeps_native_device_tree(self):
        actual, wifi_flag = self.apply_mode("YES")
        self.assertEqual(read(SOURCE, DTS_FILE), actual)
        self.assertEqual("WRT_WIFI=wifi-yes", wifi_flag)

    def test_no_changes_only_q6_memory_include(self):
        original = read(SOURCE, DTS_FILE)
        self.assertIn('#include "ipq8074.dtsi"', original)
        actual, wifi_flag = self.apply_mode("NO")
        self.assertEqual(original.replace("ipq8074.dtsi", "ipq8074-nowifi.dtsi"), actual)
        self.assertEqual("WRT_WIFI=wifi-no", wifi_flag)


if __name__ == "__main__":
    unittest.main()
