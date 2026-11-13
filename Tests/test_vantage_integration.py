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
BRIDGE_IMPORT = "import { read_bridge_fdb } from 'vantage_bridge';"


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
            self.assert_software_only_collector(
                original[PLUGIN].decode("utf-8").replace("\r\n", "\n"),
                (package / PLUGIN).read_text(encoding="utf-8"))
            self.assertEqual(set(original) | {MODULE},
                             {p.relative_to(package) for p in package.rglob("*") if p.is_file()})
            for path, data in original.items():
                if path != PLUGIN:
                    self.assertEqual(data, (package / path).read_bytes(), str(path))

    def assert_software_only_collector(self, original, actual):
        self.assertEqual(actual.count(BRIDGE_IMPORT), 1)
        self.assertIn("read_bridge_fdb(NET, FDB_LIMIT, FDB_ENTRY)", actual)
        before = [line for line in original.splitlines() if line.startswith("import ")]
        after = [line for line in actual.splitlines()
                 if line.startswith("import ") and line != BRIDGE_IMPORT]
        self.assertEqual(before, after)
        for obsolete in ("RTM_GETNEIGH", "AF_BRIDGE", "bridge_table", "fdb_last",
                         "fdb_le", "FDB_DUMP_S", "FDB_PARSE"):
            self.assertNotIn(obsolete, actual)
        # Keep newer upstream wireless, aliases, quiet clients and thermal code.
        first, last = "function norm_mac(v)", "function netdev(v)"
        self.assertEqual(original[original.index(first):original.index(last)],
                         actual[actual.index(first):actual.index(last)])
        # The separate route lookup still uses rtnl; only the FDB dump is removed.
        suffix = "function routes()"
        self.assertEqual(original[original.index(suffix):], actual[actual.index(suffix):])

    def test_unrelated_import_order_does_not_break_collector_adaptation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / PLUGIN
            plugin.parent.mkdir(parents=True)
            source = (SOURCE / PLUGIN).read_text(encoding="utf-8")
            imports = [line for line in source.splitlines() if line.startswith("import ")]
            original = source.replace("\n".join(imports), "\n".join(reversed(imports)))
            self.assertNotEqual(source, original)
            plugin.write_text(original, encoding="utf-8")
            run_bash(f'bash "{REPO.as_posix()}/Scripts/Vantage.sh" "$PWD"', root, {})
            self.assert_software_only_collector(original, plugin.read_text(encoding="utf-8"))

    def test_changed_upstream_query_fails_before_modifying_package(self):
        self.assert_upstream_drift_rejected(
            "rtnl.request(rtnl.const.RTM_GETNEIGH", "upstream_new_collector(rtnl.const.RTM_GETNEIGH")

    def test_missing_netlink_import_fails_before_modifying_package(self):
        self.assert_upstream_drift_rejected("import * as rtnl from 'rtnl';", "")

    def assert_upstream_drift_rejected(self, old, new):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / PLUGIN
            plugin.parent.mkdir(parents=True)
            source = (SOURCE / PLUGIN).read_text(encoding="utf-8")
            self.assertIn(old, source)
            original = source.replace(old, new)
            plugin.write_text(original, encoding="utf-8")
            with self.assertRaises(subprocess.CalledProcessError):
                run_bash(f'bash "{REPO.as_posix()}/Scripts/Vantage.sh" "$PWD"', root, {})
            self.assertEqual(original, plugin.read_text(encoding="utf-8"))
            self.assertFalse((root / MODULE).exists())


if __name__ == "__main__":
    unittest.main()
