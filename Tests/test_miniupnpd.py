"""Validate the official-source override using a real feed package and archive."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
PACKAGE = Path(os.environ["MINIUPNPD_PACKAGE_CHECK"])
ARCHIVE = Path(os.environ["MINIUPNPD_ARCHIVE_CHECK"])
BASH = os.environ.get("BASH", "bash")
COMMAND_TIMEOUT = 60
COMMIT = "2dcf63959950dbb2c3f97b7bd63773d499749134"


def run_script(package):
    return subprocess.run(
        [BASH, str(REPO / "Scripts/Miniupnpd.sh"), package.as_posix()],
        text=True, capture_output=True, timeout=COMMAND_TIMEOUT,
    )


class MiniupnpdSourceTests(unittest.TestCase):
    def test_real_package_integration_is_preserved_and_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "miniupnpd"
            shutil.copytree(PACKAGE, package)
            originals = {p.relative_to(package): p.read_bytes()
                         for p in package.rglob("*") if p.is_file()}
            for _ in range(2):
                result = run_script(package)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for path, content in originals.items():
                if path != Path("Makefile"):
                    self.assertEqual((package / path).read_bytes(), content, str(path))
            recipe = (package / "Makefile").read_text(encoding="utf-8")
            include = "include ./ci-source.mk\n"
            self.assertEqual(recipe.count(include), 1)
            self.assertLess(recipe.index(include), recipe.index("include $(INCLUDE_DIR)/package.mk"))
            original = originals[Path("Makefile")].decode().replace("\r\n", "\n")
            self.assertEqual(recipe.replace(include, ""), original)

    def test_unknown_recipe_layout_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "Makefile").write_text("PKG_NAME:=miniupnpd\n", encoding="utf-8")
            result = run_script(package)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source override", result.stderr)

    def test_pinned_archive_checksum_and_recovery_fix(self):
        pin = (REPO / "Config/miniupnpd-source.mk").read_text(encoding="utf-8")
        metadata = dict(line.split(":=", 1) for line in pin.splitlines() if ":=" in line)
        self.assertEqual(metadata["PKG_SOURCE_VERSION"], COMMIT)
        self.assertEqual(metadata["PKG_RELEASE"], "2")
        self.assertEqual(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(), metadata["PKG_HASH"])
        with tarfile.open(ARCHIVE, "r:gz") as archive:
            source = archive.extractfile(f"miniupnp-{COMMIT}/miniupnpd/miniupnpd.c").read().decode()
        self.assertIn("(!reserved || GETFLAG(ALLOWPRIVATEIPV4MASK))", source)
        self.assertIn("/miniupnpd", metadata["PKG_BUILD_DIR"])
        self.assertIn("TAR_OPTIONS+= --strip-components 1", pin)
        self.assertIn("https://codeload.github.com/miniupnp/miniupnp/", pin)

    def test_both_build_modes_use_source_override(self):
        workflow = (REPO / ".github/workflows/WRT-CORE.yml").read_text(encoding="utf-8")
        self.assertIn("$GITHUB_WORKSPACE/Scripts/Miniupnpd.sh", workflow)
        self.assertLess(workflow.index("Scripts/Miniupnpd.sh"), workflow.index("name: Custom Settings"))

    def test_feed_patches_apply_to_real_archive_layout(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build = root / "miniupnpd"
            build.mkdir()
            result = subprocess.run(
                [BASH, "-o", "pipefail", "-c",
                 'gzip -dc "$1" | tar -xf - -C "$2/.." --strip-components 1',
                 "test-unpack", ARCHIVE.as_posix(), build.as_posix()],
                text=True, capture_output=True, timeout=COMMAND_TIMEOUT,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((build / "configure").is_file())
            for patch in sorted((PACKAGE / "patches").glob("*.patch")):
                result = subprocess.run(
                    [BASH, "-c", 'patch --batch --forward --fuzz=0 -p1 -d "$1" < "$2"',
                     "test-feed-patch", build.as_posix(), patch.as_posix()],
                    text=True, capture_output=True, timeout=COMMAND_TIMEOUT,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            source = (build / "miniupnpd.c").read_text(encoding="utf-8")
            self.assertIn("(!reserved || GETFLAG(ALLOWPRIVATEIPV4MASK))", source)


if __name__ == "__main__":
    unittest.main()
