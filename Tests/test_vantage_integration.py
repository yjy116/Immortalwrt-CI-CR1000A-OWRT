"""Exercise the package transform, including its upstream-drift failure path."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

from test_compatibility import REPO, run_bash

SOURCE = Path(os.environ["WRT_VANTAGE_CHECK"])
PLUGIN = Path("luci-app-vantage/root/usr/share/rpcd/ucode/luci.vantage")
MODULE = Path("luci-app-vantage/root/usr/share/ucode/vantage_bridge.uc")


class VantageIntegrationTests(unittest.TestCase):
    def test_shared_workflow_installs_collector_without_changing_other_package_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "wrt/package/luci-theme-vantage"
            shutil.copytree(SOURCE / "luci-app-vantage", package / "luci-app-vantage")
            original = {p.relative_to(package): p.read_bytes()
                        for p in package.rglob("*") if p.is_file()}
            scripts = root / "Scripts"
            scripts.mkdir()
            for name in ("Packages.sh", "Handles.sh", "UpnpSource.sh"):
                path = scripts / name
                path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                path.chmod(0o755)
            shutil.copyfile(REPO / "Scripts/Vantage.sh", scripts / "Vantage.sh")
            shutil.copytree(REPO / "Patches/vantage", root / "Patches/vantage")
            workflow = yaml.safe_load((REPO / ".github/workflows/WRT-CORE.yml").read_text(encoding="utf-8"))
            steps = next(job["steps"] for job in workflow["jobs"].values() if "steps" in job)
            code = next(step["run"] for step in steps if step.get("name") == "Custom Packages")
            try:
                run_bash("set -e\n" + code, root, {"GITHUB_WORKSPACE": root.as_posix()})
            except subprocess.CalledProcessError as error:
                self.fail(error.stdout + error.stderr)
            self.assertEqual((REPO / "Patches/vantage/vantage_bridge.uc").read_bytes(),
                             (package / MODULE).read_bytes())
            self.assertNotEqual(original[PLUGIN], (package / PLUGIN).read_bytes())
            self.assertEqual(set(original) | {MODULE},
                             {p.relative_to(package) for p in package.rglob("*") if p.is_file()})
            for path, data in original.items():
                if path != PLUGIN:
                    self.assertEqual(data, (package / path).read_bytes(), str(path))

    def test_changed_upstream_query_fails_before_modifying_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / PLUGIN
            plugin.parent.mkdir(parents=True)
            original = (SOURCE / PLUGIN).read_text(encoding="utf-8").replace(
                "rtnl.request(rtnl.const.RTM_GETNEIGH", "upstream_new_collector(rtnl.const.RTM_GETNEIGH")
            plugin.write_text(original, encoding="utf-8")
            with self.assertRaises(subprocess.CalledProcessError):
                run_bash(f'bash "{REPO.as_posix()}/Scripts/Vantage.sh" "$PWD"', root, {})
            self.assertEqual(original, plugin.read_text(encoding="utf-8"))
            self.assertFalse((root / MODULE).exists())


if __name__ == "__main__":
    unittest.main()
