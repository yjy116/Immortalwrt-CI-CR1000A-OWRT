"""Check the actual CI validator against both firmware modes and real upstream."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from test_compatibility import REPO, SOURCE, run_bash


REQUIRED = (
    "kmod-dsa-rtl9303-spi", "cr1000a-recovery", "kmod-nss-wifi-drv",
    "nss-firmware", "luci-app-qca-ppe-qos", "qca-ppe-qos",
)
RADIOS = ("kmod-ath11k", "kmod-ath11k-ahb", "kmod-ath11k-pci")


def config(mode):
    lines = [f"CONFIG_PACKAGE_{name}=y" for name in REQUIRED]
    lines += ["CONFIG_TARGET_MULTI_PROFILE=y", "CONFIG_TARGET_PER_DEVICE_ROOTFS=y"]
    if mode == "YES":
        lines += [f"CONFIG_PACKAGE_{name}=y" for name in RADIOS]
        lines += ["CONFIG_ATH11K_NSS_WIFI=y"]
    else:
        # Values observed in the published WiFi-NO defconfig (2026-10-22).
        lines += ["CONFIG_PACKAGE_kmod-ath11k=m", "CONFIG_PACKAGE_kmod-ath11k-ahb=m",
                  "CONFIG_PACKAGE_kmod-ath11k-pci=m"]
    return "\n".join(lines) + "\n"


class PpeNssTests(unittest.TestCase):
    def validate(self, kind, content, mode="YES"):
        script = REPO / "Scripts/CheckOwrt.sh"
        self.assertTrue(script.is_file(), "Native PPE/NSS validation is missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "input").write_text(content, encoding="utf-8")
            return run_bash(f'bash "{script.as_posix()}" {kind} input', root,
                            {"WRT_CONFIG": f"CR1000A-WIFI-{mode}"})

    def test_both_modes_accept_native_acceleration_and_qos(self):
        for mode in ("YES", "NO"):
            self.validate("config", config(mode), mode)

    def test_required_package_omissions_are_named(self):
        for package in REQUIRED:
            with self.subTest(package=package):
                content = config("YES").replace(f"CONFIG_PACKAGE_{package}=y\n", "")
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    self.validate("config", content)
                self.assertIn(package, error.exception.stdout)

    def test_yes_requires_nss_wlan_integration(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.validate("config", config("YES").replace("CONFIG_ATH11K_NSS_WIFI=y", ""))

    def test_no_accepts_compiled_modules_with_nss_build_integration(self):
        self.validate("config", config("NO") + "CONFIG_ATH11K_NSS_WIFI=y\n", "NO")

    def test_no_rejects_built_in_radios(self):
        for package in RADIOS:
            with self.subTest(package=package):
                content = config("NO").replace(f"CONFIG_PACKAGE_{package}=m",
                                               f"CONFIG_PACKAGE_{package}=y")
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    self.validate("config", content, "NO")
                self.assertIn(package, error.exception.stdout)

    def test_yes_accepts_device_modules_but_requires_each_driver(self):
        content = config("YES")
        for package in RADIOS:
            content = content.replace(f"CONFIG_PACKAGE_{package}=y", f"CONFIG_PACKAGE_{package}=m")
        self.validate("config", content)
        for package in RADIOS:
            with self.subTest(package=package):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.validate("config", content.replace(f"CONFIG_PACKAGE_{package}=m\n", ""))

    def test_yes_base_manifest_does_not_require_device_only_packages(self):
        manifest = "".join(f"{package} - 1.0-r1\n" for package in REQUIRED)
        self.validate("manifest", manifest)

    def test_manifest_verifies_real_packages_not_only_configuration(self):
        manifest = "".join(f"{package} - 1.0-r1\n" for package in (*REQUIRED, *RADIOS))
        self.validate("manifest", manifest)
        no_manifest = "".join(f"{package} - 1.0-r1\n" for package in REQUIRED)
        self.validate("manifest", no_manifest, "NO")
        for package in REQUIRED:
            with self.subTest(package=package):
                with self.assertRaises(subprocess.CalledProcessError):
                    self.validate("manifest", manifest.replace(f"{package} - 1.0-r1\n", ""))

    def test_no_manifest_rejects_wireless_packages(self):
        manifest = "".join(f"{package} - 1.0-r1\n" for package in REQUIRED)
        with self.assertRaises(subprocess.CalledProcessError):
            self.validate("manifest", manifest + "kmod-ath11k - 1.0-r1\n", "NO")

    def test_new_packages_use_native_upstream_providers(self):
        target = (SOURCE / "target/linux/qualcommax/Makefile").read_text(encoding="utf-8")
        self.assertIn("kmod-nss-wifi-drv", target)
        ath = (SOURCE / "package/kernel/mac80211/ath.mk").read_text(encoding="utf-8")
        self.assertIn("config ATH11K_NSS_WIFI", ath)
        for path in ("package/qca-nss/nss-wifi-drv", "package/qca-nss/nss-firmware",
                     "package/emortal/luci-app-qca-ppe-qos", "package/network/config/qca-ppe-qos"):
            self.assertTrue((SOURCE / path / "Makefile").is_file(), path)
        extras = (REPO / "Config/EXTRA.txt").read_text(encoding="utf-8")
        self.assertIn("CONFIG_PACKAGE_luci-app-qca-ppe-qos=y", extras)
        self.assertIn("CONFIG_PACKAGE_sqm-scripts=y", extras)


if __name__ == "__main__":
    unittest.main()
