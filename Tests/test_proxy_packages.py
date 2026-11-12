"""Prepare real released packages through the production shell entry points."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from test_compatibility import BASH, REPO
from test_release_source import TIMEOUT, git


FIXTURES = {"daede": Path(os.environ["WRT_DAEDE_UPSTREAM"]),
            "honk": Path(os.environ["WRT_HONK_UPSTREAM"])}
UPSTREAM_HEADER_LINES = 30


def selection(package, *, fixture=None):
    repository = f"kenzok8/openwrt-{package}"
    return {
        "repository": repository, "tag": "v2026.11.04-test",
        "release_id": 42, "published_at": "2026-11-04T00:00:00Z",
        "url": f"https://github.com/{repository}/releases/tag/v2026.11.04-test",
        "commit": git(fixture or FIXTURES[package], "rev-parse", "HEAD").strip(),
    }


def prepare(package, destination, *, fixture=None):
    name = "Daede" if package == "daede" else "Honk"
    source = fixture or FIXTURES[package]
    environment = {
        **os.environ, "GITHUB_WORKSPACE": REPO.as_posix(),
        "WRT_PROXY_RELEASES": json.dumps({package: selection(package, fixture=source)}),
        "WRT_PYTHON": Path(sys.executable).as_posix(),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": f"url.{source.as_uri()}.insteadOf",
        "GIT_CONFIG_VALUE_0": f"https://github.com/kenzok8/openwrt-{package}.git",
    }
    command = ('python3() { "$WRT_PYTHON" "$@"; }; export -f python3\n'
               f'bash "{REPO.as_posix()}/Scripts/{name}.sh" "{destination.as_posix()}"')
    return subprocess.run([BASH, "-s"], input=command, text=True,
                          capture_output=True, env=environment, timeout=TIMEOUT)


class ProxyPackageTests(unittest.TestCase):
    def test_daede_migration_stays_in_install_block_when_upstream_lines_move(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "upstream", root / "prepared"
            git(root, "-c", "core.autocrlf=false", "clone", "--quiet",
                str(FIXTURES["daede"]), str(source))
            recipe = source / "luci-app-daede/Makefile"
            header = "# Upstream added documentation before package definitions\n" * UPSTREAM_HEADER_LINES
            recipe.write_text(header + recipe.read_text(encoding="utf-8"),
                              encoding="utf-8", newline="\n")
            git(source, "add", "luci-app-daede/Makefile")
            git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-qm", "Move package definitions without changing semantics")
            result = prepare("daede", destination, fixture=source)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            prepared = (destination / "luci-app-daede/Makefile").read_text(encoding="utf-8")
            install = re.search(r"^define Package/\$\(PKG_NAME\)/install\n(.*?)^endef$",
                                prepared, re.M | re.S)
            self.assertIsNotNone(install)
            self.assertIn("$(INSTALL_BIN) ./root/etc/uci-defaults/89-daede-migrate",
                          install.group(1))

    def test_daede_rejects_changed_install_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "upstream", root / "prepared"
            git(root, "-c", "core.autocrlf=false", "clone", "--quiet",
                str(FIXTURES["daede"]), str(source))
            recipe = source / "luci-app-daede/Makefile"
            original = recipe.read_text(encoding="utf-8")
            changed = original.replace("$(INSTALL_DIR) $(1)/etc/uci-defaults",
                                       "install -d $(1)/etc/uci-defaults")
            self.assertNotEqual(original, changed)
            recipe.write_text(changed, encoding="utf-8", newline="\n")
            git(source, "add", "luci-app-daede/Makefile")
            git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-qm", "Change migration installation context")
            result = prepare("daede", destination, fixture=source)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("FAILED", result.stdout + result.stderr)
            self.assertFalse((destination / "ci/DAEDE-SOURCE.txt").exists())

    def test_honk_rejects_missing_archive_hash_without_success_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, destination = root / "upstream", root / "prepared"
            git(root, "-c", "core.autocrlf=false", "clone", "--quiet",
                str(FIXTURES["honk"]), str(source))
            recipe = source / "honk/Makefile"
            text = recipe.read_text(encoding="utf-8")
            lines = ["HONK_HASH_AARCH64?=SKIP" if line.startswith("HONK_HASH_AARCH64?=")
                     else line for line in text.splitlines()]
            recipe.write_text("\n".join(lines), encoding="utf-8", newline="\n")
            git(source, "add", "honk/Makefile")
            git(source, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "-qm", "Break archive checksum")
            result = prepare("honk", destination, fixture=source)
            self.assertNotEqual(0, result.returncode)
            self.assertIn("HONK_HASH_AARCH64", result.stdout + result.stderr)
            self.assertFalse((destination / "ci/HONK-SOURCE.txt").exists())

    def test_daede_release_keeps_migration_and_coexistence_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "daede"
            result = prepare("daede", destination)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            record = (destination / "ci/DAEDE-SOURCE.txt").read_text()
            self.assertIn(selection("daede")["commit"], record)
            self.assertIn("PACKAGING_TAG=v2026.11.04-test", record)
            migration = destination / "luci-app-daede/root/etc/uci-defaults/89-daede-migrate"
            self.assertEqual((REPO / "files/etc/uci-defaults/89-daede-migrate").read_bytes(),
                             migration.read_bytes())
            for test in ("test_daede_service_guard.sh", "test_honk_coexistence.sh"):
                command = [BASH, str(REPO / "Tests" / test), str(destination)]
                if test == "test_honk_coexistence.sh":
                    command.append(os.environ["WRT_HONK_CHECK"])
                checked = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT)
                self.assertEqual(0, checked.returncode, checked.stdout + checked.stderr)
            self.assertFalse(list(destination.rglob("*.orig")))
            self.assertFalse(list(destination.rglob("*.rej")))

    def test_honk_uses_native_matched_recipes_without_old_stage_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "honk"
            result = prepare("honk", destination)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            for path in ("honk/Makefile", "luci-app-honk/Makefile", "ci/pins.env"):
                self.assertEqual((FIXTURES["honk"] / path).read_bytes(),
                                 (destination / path).read_bytes())
            self.assertFalse((destination / "honk/generated-stage.mk").exists())
            self.assertFalse((destination / "luci-app-honk/generated-doona-stage.mk").exists())
            check = subprocess.run([BASH, str(REPO / "Tests/test_honk_reclaim.sh"),
                                    str(destination)], capture_output=True, text=True,
                                   timeout=TIMEOUT)
            self.assertEqual(0, check.returncode, check.stdout + check.stderr)
            record = (destination / "ci/HONK-SOURCE.txt").read_text()
            self.assertIn(selection("honk")["commit"], record)
            for key, path in (("HONK_MAKEFILE_SHA256", "honk/Makefile"),
                              ("LUCI_HONK_MAKEFILE_SHA256", "luci-app-honk/Makefile"),
                              ("HONK_LIFECYCLE_SHA256", "honk/files/lifecycle.sh")):
                checksum = hashlib.sha256((destination / path).read_bytes()).hexdigest()
                self.assertIn(f"{key}={checksum}", record)
            patch_file = REPO / "Patches/honk/010-shared-datapath-ownership.patch"
            patch_hash = hashlib.sha256(patch_file.read_bytes()).hexdigest()
            self.assertIn(f"HONK_COEXISTENCE_PATCH_SHA256={patch_hash}", record)


if __name__ == "__main__":
    unittest.main()
