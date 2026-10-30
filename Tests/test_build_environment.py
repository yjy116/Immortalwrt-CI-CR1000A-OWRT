"""Audit host dependency setup against the inspected upstream CI template."""

import os
from pathlib import Path
import shlex
import unittest

import yaml


REPO = Path(__file__).resolve().parents[1]
TEMPLATE = Path(os.environ["WRT_CI_TEMPLATE"])


def initialization(root):
    workflow = yaml.safe_load((root / ".github/workflows/WRT-CORE.yml").read_text(encoding="utf-8"))
    return next(step for step in workflow["jobs"]["core"]["steps"]
                if step["name"] == "Initialization Environment")


def apt_packages(code):
    packages = set()
    for line in code.replace("\\\n", " ").splitlines():
        command = shlex.split(line)
        if command[:2] == ["sudo", "apt-get"] and "install" in command:
            packages.update(token for token in command[command.index("install") + 1:]
                            if not token.startswith("-"))
    return packages


class BuildEnvironmentTests(unittest.TestCase):
    def test_direct_install_includes_upstream_dependencies_and_existing_fuse(self):
        expected = apt_packages(initialization(TEMPLATE)["run"])
        self.assertTrue(expected, "Upstream APT package list was not found")
        self.assertEqual(expected | {"libfuse-dev"}, apt_packages(initialization(REPO)["run"]))

    def test_remote_os_allowlist_and_full_upgrade_are_not_used(self):
        step = initialization(REPO)
        self.assertNotIn("init_build_environment.sh", step["run"])
        self.assertNotIn("full-upgrade", step["run"])
        self.assertEqual("noninteractive", step["env"]["DEBIAN_FRONTEND"])


if __name__ == "__main__":
    unittest.main()
