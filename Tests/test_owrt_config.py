"""Exercise the workflow's post-defconfig check, not a reimplemented validator."""

import json
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

import yaml

from test_compatibility import REPO, run_bash


REQUIRED_PACKAGES = ("kmod-dsa-rtl9303-spi", "cr1000a-recovery")


def workflow(name):
    return yaml.safe_load((REPO / ".github/workflows" / name).read_text(encoding="utf-8"))


class OwrtConfigTests(unittest.TestCase):
    def check_config(self, packages):
        steps = workflow("WRT-CORE.yml")["jobs"]["core"]["steps"]
        settings = next(step["run"] for step in steps if step["name"] == "Custom Settings")
        validation = settings.split("make defconfig", 1)[1].split("\n", 1)[1]
        validation = validation.split('echo "BPF/LLVM', 1)[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = "".join(f"CONFIG_PACKAGE_{package}=y\n" for package in packages)
            (root / ".config").write_text(config, encoding="utf-8")
            return run_bash(validation, root, {})

    def test_dsa_and_recovery_config_is_accepted(self):
        self.check_config(REQUIRED_PACKAGES)

    def test_missing_native_packages_fail_with_explicit_package_name(self):
        for missing in REQUIRED_PACKAGES:
            with self.subTest(missing=missing):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    self.check_config(package for package in REQUIRED_PACKAGES if package != missing)
                self.assertIn(missing, error.exception.stdout)

    def test_legacy_support_cannot_substitute_for_owrt_driver(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.check_config(["cr1000a-support"])

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
