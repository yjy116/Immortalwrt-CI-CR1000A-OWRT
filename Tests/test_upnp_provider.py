"""Verify single-provider UPnP integration using the actual upstream checkout."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import yaml

from test_compatibility import REPO, run_bash


UPSTREAM = Path(os.environ["WRT_VIKING_PACKAGES"])
SCRIPT = REPO / "Scripts/UpnpSource.sh"


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for name in ("miniupnpd", "luci-app-upnp")
            for path in (root / name).rglob("*") if path.is_file()}


def clone_fixture(root):
    subprocess.run(["git", "clone", "--quiet", "--no-hardlinks", str(UPSTREAM), str(root)],
                   check=True, capture_output=True, timeout=60)


class UpnpProviderTests(unittest.TestCase):
    def test_package_update_removes_both_old_feed_providers(self):
        source = (REPO / "Scripts/Packages.sh").read_text(encoding="utf-8")
        function = source[source.index("UPDATE_PACKAGE() {"):source.index("# 调用示例")]
        call = next(line for line in source.splitlines() if line.startswith('UPDATE_PACKAGE "viking"'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = (root / "feeds/packages/net/miniupnpd", root / "feeds/luci/applications/luci-app-upnp")
            for path in old:
                path.mkdir(parents=True)
                (path / "Makefile").write_text("old feed provider\n", encoding="utf-8")
            (root / "package").mkdir()
            # Replace only the network transport, keeping the real cloning and update logic.
            transport = 'git() { command git clone --quiet "$WRT_VIKING_PACKAGES" "${@: -1}"; }\n'
            run_bash("set -e\n" + transport + function + call, root,
                     {"WRT_VIKING_PACKAGES": UPSTREAM.as_posix()})
            for path in old:
                self.assertFalse(path.exists(), f"Duplicate package source: {path}")
            self.assertEqual(snapshot(UPSTREAM), snapshot(root / "package/packages"))

    def test_records_match_both_packages_without_modifying_upstream(self):
        self.assertTrue(SCRIPT.is_file(), "Upstream pair provenance script is missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages, output = root / "packages", root / "records"
            clone_fixture(packages)
            original = snapshot(packages)
            command = f'bash "{SCRIPT.as_posix()}" "{packages.as_posix()}" "{output.as_posix()}"'
            run_bash(command, root, {})
            expected_commit = subprocess.check_output(
                ["git", "-C", str(packages), "rev-parse", "HEAD"], text=True).strip()
            for name, filename in (("miniupnpd", "MINIUPNPD-SOURCE.txt"),
                                   ("luci-app-upnp", "LUCI-UPNP-SOURCE.txt")):
                values = dict(line.split("=", 1) for line in (output / filename).read_text().splitlines())
                self.assertEqual("VIKINGYFY/packages", values["provider"])
                self.assertEqual(expected_commit, values["provider_commit"])
                recipe = packages / name / "Makefile"
                self.assertEqual(hashlib.sha256(recipe.read_bytes()).hexdigest(), values["makefile_sha256"])
            self.assertEqual(original, snapshot(packages))
            core = dict(line.split("=", 1) for line in
                        (output / "MINIUPNPD-SOURCE.txt").read_text().splitlines())
            recipe = (packages / "miniupnpd/Makefile").read_text()
            self.assertIn(f'PKG_SOURCE_VERSION:={core["source_commit"]}', recipe)
            self.assertIn(f'PKG_HASH:={core["source_sha256"]}', recipe)

    def test_missing_paired_package_is_reported(self):
        self.assertTrue(SCRIPT.is_file(), "Upstream pair provenance script is missing")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packages = root / "packages"
            clone_fixture(packages)
            shutil.rmtree(packages / "luci-app-upnp")
            command = f'bash "{SCRIPT.as_posix()}" "{packages.as_posix()}" "{root.as_posix()}/records"'
            with self.assertRaises(subprocess.CalledProcessError):
                run_bash(command, root, {})

    def test_common_workflow_uses_only_upstream_provenance(self):
        path = REPO / ".github/workflows/WRT-CORE.yml"
        steps = yaml.safe_load(path.read_text(encoding="utf-8"))["jobs"]["core"]["steps"]
        commands = {step["name"]: step.get("run", "") for step in steps}
        custom = commands["Custom Packages"]
        self.assertNotIn("Scripts/Miniupnpd.sh", custom)
        self.assertNotIn("Scripts/LuciUpnp.sh", custom)
        self.assertIn("Scripts/UpnpSource.sh", custom)
        self.assertIn("./tmp/upnp-source/*.txt", commands["Package Firmware"])


if __name__ == "__main__":
    unittest.main()
