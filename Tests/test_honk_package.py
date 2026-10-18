"""Validate pinned Honk/Doona packaging prepared by Scripts/Honk.sh."""

import json
import os
from pathlib import Path
import unittest

from test_compatibility import REPO, SOURCE


HONK = Path(os.environ["WRT_HONK_CHECK"])
CORE_COMMIT = "0e61ed382c6746773d11e78a9f81a8092aa33c62"
ASSET_RELEASE = "source-39098804282"


def assignments(path):
    return dict(line.split(":=", 1) for line in path.read_text(encoding="utf-8").splitlines()
                if ":=" in line and not line.startswith("#"))


class HonkPackageTests(unittest.TestCase):
    def test_packages_and_kernel_prerequisites_are_selected(self):
        config = (REPO / "Config/EXTRA.txt").read_text(encoding="utf-8").splitlines()
        for option in ("PACKAGE_honk", "PACKAGE_luci-app-honk", "KERNEL_FTRACE",
                       "KERNEL_FUNCTION_TRACER", "KERNEL_DYNAMIC_FTRACE",
                       "KERNEL_DEBUG_INFO_BTF", "DAE_USE_KERNEL_BTF", "DAED_USE_KERNEL_BTF"):
            self.assertIn(f"CONFIG_{option}=y", config)
        self.assertNotIn("CONFIG_PACKAGE_vmlinux-btf=y", config)
        kernel = (SOURCE / "config/Config-kernel.in").read_text(encoding="utf-8")
        for option in ("FTRACE", "FUNCTION_TRACER", "DYNAMIC_FTRACE"):
            self.assertIn(f"config KERNEL_{option}\n", kernel)

    def test_source_preparation_is_wired_into_packages(self):
        script = REPO / "Scripts/Honk.sh"
        self.assertTrue(script.is_file())
        self.assertIn('Scripts/Honk.sh', (REPO / "Scripts/Packages.sh").read_text(encoding="utf-8"))

    def test_required_release_metadata_is_present_and_hashed(self):
        core_stage = HONK / "honk/generated-stage.mk"
        ui_stage = HONK / "luci-app-honk/generated-doona-stage.mk"
        provenance = HONK / "honk/generated-provenance.json"
        for path in (core_stage, ui_stage, provenance):
            self.assertTrue(path.is_file(), str(path))
        core = assignments(core_stage)
        ui = assignments(ui_stage)
        self.assertIn(CORE_COMMIT, core["HONK_ASSET_AARCH64"])
        for data, hash_key in ((core, "HONK_HASH_AARCH64"), (ui, "PKG_HASH")):
            self.assertRegex(data[hash_key], r"^[0-9a-f]{64}$")
            self.assertIn(f"/download/{ASSET_RELEASE}", data["PKG_SOURCE_URL"])
        details = json.loads(provenance.read_text(encoding="utf-8"))
        self.assertEqual(CORE_COMMIT, details["core"]["commit"])
        self.assertEqual("https://github.com/Glassyiris/honk.git", details["core"]["repository"])

    def test_honk_is_opt_in_and_doona_is_bundled(self):
        config = (HONK / "honk/files/honk.config").read_text(encoding="utf-8")
        for option in ("enabled", "boot_enabled", "initialized"):
            self.assertRegex(config, rf"option {option}\s+'0'")
        makefile = (HONK / "luci-app-honk/Makefile").read_text(encoding="utf-8")
        self.assertIn("/usr/share/doona", makefile)
        self.assertIn("honk.zh-cn.lmo", makefile)
        self.assertIn("+honk", makefile)
        self.assertNotRegex(makefile, r"include .*rust|cargo build|pnpm build")


if __name__ == "__main__":
    unittest.main()
