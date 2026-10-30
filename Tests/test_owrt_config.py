"""Exercise the workflow's post-defconfig check, not a reimplemented validator."""

from contextlib import nullcontext
from itertools import product
import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

import yaml

from test_compatibility import REPO, run_bash
from test_ppe_nss import REQUIRED, config


REQUIRED_PACKAGES = REQUIRED


def workflow(name):
    return yaml.safe_load((REPO / ".github/workflows" / name).read_text(encoding="utf-8"))


class OwrtConfigTests(unittest.TestCase):
    def check_config(self, packages, mode="YES"):
        steps = workflow("WRT-CORE.yml")["jobs"]["core"]["steps"]
        settings = next(step["run"] for step in steps if step["name"] == "Custom Settings")
        validation = settings.split("make defconfig", 1)[1].split("\n", 1)[1]
        validation = validation.split('echo "BPF/LLVM', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            content = config(mode)
            for package in set(REQUIRED_PACKAGES) - set(packages):
                content = content.replace(f"CONFIG_PACKAGE_{package}=y\n", "")
            (root / ".config").write_text(content, encoding="utf-8")
            return run_bash(validation, root, {
                "GITHUB_WORKSPACE": REPO.as_posix(), "WRT_CONFIG": f"CR1000A-WIFI-{mode}",
            })

    def test_dsa_and_recovery_config_is_accepted(self):
        self.check_config(REQUIRED_PACKAGES)

    def test_no_defconfig_with_compiled_modules_is_accepted(self):
        self.check_config(REQUIRED_PACKAGES, "NO")

    def test_missing_native_packages_fail_with_explicit_package_name(self):
        for missing in REQUIRED_PACKAGES:
            with self.subTest(missing=missing):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    self.check_config(package for package in REQUIRED_PACKAGES if package != missing)
                self.assertIn(missing, error.exception.stdout)

    def test_legacy_support_cannot_substitute_for_owrt_driver(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.check_config(["cr1000a-support"])

    def test_release_checks_base_manifest_without_assuming_device_packages(self):
        steps = workflow("WRT-CORE.yml")["jobs"]["core"]["steps"]
        packaging = next(step["run"] for step in steps if step["name"] == "Package Firmware")
        validation = "mapfile -t MANIFESTS" + packaging.split("mapfile -t MANIFESTS", 1)[1]
        validation = validation.split('echo "WRT_KVER=', 1)[0]
        manifest = "".join(f"{name} - 1.0-r1\n" for name in REQUIRED_PACKAGES)
        scenarios = (None, manifest, manifest.replace("\nqca-ppe-qos - 1.0-r1\n", "\n"),
                     manifest + "kmod-ath11k - 1.0-r1\n")
        for mode, content in product(("YES", "NO"), scenarios):
            with self.subTest(mode=mode, content=content), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                target = root / "bin/targets/qualcommax/ipq807x"
                target.mkdir(parents=True)
                if content is not None:
                    (target / "cr1000a.manifest").write_text(content, encoding="utf-8")
                environment = {"GITHUB_WORKSPACE": REPO.as_posix(),
                               "WRT_CONFIG": f"CR1000A-WIFI-{mode}"}
                valid = content == manifest or (mode == "YES" and content == scenarios[-1])
                outcome = nullcontext() if valid else self.assertRaises(subprocess.CalledProcessError)
                with outcome:
                    run_bash(validation, root, environment)

    def test_scheduler_watches_fork_owrt_but_dispatches_ci_main(self):
        jobs = workflow("Auto-Build.yml")["jobs"]
        steps = jobs["check_updates"]["steps"]
        check = next(step for step in steps if step.get("id") == "check")
        self.assertEqual("yjy116/immortalwrt", check["env"]["SOURCE"])
        self.assertEqual("owrt", check["env"]["BRANCH"])
        dispatch = jobs["trigger_build"]["steps"][0]["run"]
        payload = shlex.split(dispatch.split("-d ", 1)[1])[0]
        self.assertEqual("main", json.loads(payload)["ref"])


if __name__ == "__main__":
    unittest.main()
