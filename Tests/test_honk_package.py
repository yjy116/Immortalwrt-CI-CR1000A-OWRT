"""Validate native release metadata prepared by Scripts/Honk.sh."""

import hashlib
import os
from pathlib import Path
import re
import unittest

from test_compatibility import REPO, SOURCE


HONK = Path(os.environ["WRT_HONK_CHECK"])


def assignments(path):
    return dict(re.findall(r"^([A-Z0-9_]+)[?:]?=(.*)$", path.read_text(encoding="utf-8"), re.M))


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
        core = assignments(HONK / "honk/Makefile")
        ui = assignments(HONK / "luci-app-honk/Makefile")
        pins = assignments(HONK / "ci/pins.env")
        self.assertEqual(pins["CORE_COMMIT"], core["CORE_COMMIT"])
        self.assertEqual("https://github.com/daeuniverse/honk.git", pins["CORE_REPOSITORY"])
        self.assertEqual(pins["DOONA_ARCHIVE"], ui["PKG_SOURCE"])
        self.assertRegex(core["HONK_SOURCE_TAG"], r"^source-[0-9]+$")
        self.assertEqual(core["HONK_SOURCE_TAG"], ui["HONK_SOURCE_TAG"])
        for data, hash_key in ((core, "HONK_HASH_AARCH64"), (ui, "PKG_HASH")):
            self.assertRegex(data[hash_key], r"^[0-9a-f]{64}$")
        record = assignments(HONK / "ci/HONK-SOURCE.txt")
        self.assertRegex(record["PACKAGING_TAG"], r"^v[0-9]")
        self.assertEqual(hashlib.sha256((HONK / "honk/Makefile").read_bytes()).hexdigest(),
                         record["HONK_MAKEFILE_SHA256"])

    def test_honk_is_opt_in_and_doona_is_bundled(self):
        config = (HONK / "honk/files/honk.config").read_text(encoding="utf-8")
        for option in ("enabled", "initialized"):
            self.assertRegex(config, rf"option {option}\s+'0'")
        makefile = (HONK / "luci-app-honk/Makefile").read_text(encoding="utf-8")
        self.assertIn("/usr/share/doona", makefile)
        self.assertIn("honk.zh-cn.lmo", makefile)
        self.assertIn("+honk", makefile)
        self.assertNotRegex(makefile, r"include .*rust|cargo build|pnpm build")


if __name__ == "__main__":
    unittest.main()
