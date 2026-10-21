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
PACKAGING_ARCHIVE = Path(os.environ["MINIUPNPD_PACKAGING_ARCHIVE"])
BASH = os.environ.get("BASH", "bash")
COMMAND_TIMEOUT = 60
COMMIT = "2dcf63959950dbb2c3f97b7bd63773d499749134"


def run_script(package, *, environment=None):
    env = dict(os.environ, MINIUPNPD_PACKAGING_ARCHIVE=PACKAGING_ARCHIVE.as_posix())
    env.update(environment or {})
    return subprocess.run(
        [BASH, str(REPO / "Scripts/Miniupnpd.sh"), package.as_posix()],
        text=True, capture_output=True, timeout=COMMAND_TIMEOUT, env=env,
    )


def package_files(package, *, normalize_newlines=False):
    files = {p.relative_to(package): p.read_bytes() for p in package.rglob("*") if p.is_file()}
    if normalize_newlines:
        return {path: content.replace(b"\r\n", b"\n") for path, content in files.items()}
    return files


def make_future_package(root):
    package = root / "miniupnpd"
    shutil.copytree(PACKAGE, package)
    recipe = (package / "Makefile").read_text(encoding="utf-8")
    (package / "Makefile").write_text(
        recipe.replace("PKG_VERSION:=2.3.11", "PKG_VERSION:=2.3.12"), encoding="utf-8")
    return package


def fake_github(root, *, merge_base=COMMIT, error=False):
    # Model a future tag only at the API boundary; do not claim it exists today.
    binary = root / "bin"
    binary.mkdir()
    response = "echo 'API unavailable' >&2\nexit 1" if error else f"echo {merge_base}"
    script = binary / "gh"
    script.write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" > "$API_CALL_FILE"\n' + response + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return {"PATH": str(binary) + os.pathsep + os.environ["PATH"],
            "API_CALL_FILE": (root / "api-call.txt").as_posix()}


class MiniupnpdSourceTests(unittest.TestCase):
    def test_real_package_integration_is_preserved_and_repeatable(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "miniupnpd"
            shutil.copytree(PACKAGE, package)
            originals = package_files(package, normalize_newlines=True)
            for _ in range(2):
                result = run_script(package)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            actual = package_files(package, normalize_newlines=True)
            for path, content in originals.items():
                if path != Path("Makefile"):
                    self.assertEqual(actual[path], content, str(path))
            recipe = (package / "Makefile").read_text(encoding="utf-8")
            include = "include ./ci-source.mk\n"
            self.assertEqual(recipe.count(include), 1)
            self.assertLess(recipe.index(include), recipe.index("include $(INCLUDE_DIR)/package.mk"))
            original = originals[Path("Makefile")].decode().replace("\r\n", "\n")
            self.assertEqual(recipe.replace(include, ""), original)
            provenance = (package / "ci-source.txt").read_text()
            self.assertIn("mode=official-fix", provenance)
            self.assertIn("packaging_commit=72c7391fb2d04080afd0bfe919605749f81eb747", provenance)

    def test_changed_old_feed_packaging_is_not_mixed_with_pinned_core(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "miniupnpd"
            shutil.copytree(PACKAGE, package)
            (package / "patches/new-incompatible.patch").write_text("not for this core\n")
            (package / "files/miniupnpd.init").write_text("changed service\n")
            result = run_script(package)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse((package / "patches/new-incompatible.patch").exists())
            self.assertEqual(package_files(package, normalize_newlines=True)[Path("files/miniupnpd.init")],
                             package_files(PACKAGE, normalize_newlines=True)[Path("files/miniupnpd.init")])

    def test_older_version_uses_numeric_not_lexical_order(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory) / "miniupnpd"
            shutil.copytree(PACKAGE, package)
            recipe = (package / "Makefile").read_text(encoding="utf-8")
            (package / "Makefile").write_text(recipe.replace("2.3.11", "2.3.9"))
            result = run_script(package)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("mode=official-fix", (package / "ci-source.txt").read_text())

    def test_unknown_newer_source_requires_review_without_changing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            package = make_future_package(Path(directory))
            recipe = (package / "Makefile").read_text(encoding="utf-8")
            (package / "Makefile").write_text(recipe.replace("https://github.com/miniupnp/", "https://example.invalid/"))
            original = package_files(package)
            result = run_script(package)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review its source", result.stderr)
            self.assertEqual(package_files(package), original)

    def test_newer_fixed_feed_is_kept_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = make_future_package(root)
            original = package_files(package)
            result = run_script(package, environment=fake_github(root))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            actual = package_files(package)
            provenance = actual.pop(Path("ci-source.txt")).decode()
            self.assertEqual(actual, original)
            self.assertIn("mode=native-feed", provenance)
            self.assertIn("version=2.3.12", provenance)
            self.assertIn(COMMIT, provenance)
            self.assertIn(f"{COMMIT}...miniupnpd_2_3_12", (root / "api-call.txt").read_text())

    def test_unfixed_newer_release_is_not_silently_downgraded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = make_future_package(root)
            original = package_files(package)
            result = run_script(package, environment=fake_github(root, merge_base="0" * 40))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not contain", result.stderr)
            self.assertEqual(package_files(package), original)

    def test_api_failure_does_not_modify_newer_feed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = make_future_package(root)
            original = package_files(package)
            result = run_script(package, environment=fake_github(root, error=True))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("API unavailable", result.stderr)
            self.assertEqual(package_files(package), original)

    def test_corrupt_snapshot_is_rejected_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "miniupnpd"
            shutil.copytree(PACKAGE, package)
            original = package_files(package)
            archive = root / "corrupt.tar.gz"
            archive.write_bytes(b"corrupt")
            result = run_script(package, environment={"MINIUPNPD_PACKAGING_ARCHIVE": archive.as_posix()})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("checksum", result.stderr)
            self.assertEqual(package_files(package), original)

    def test_unknown_recipe_layout_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            package = Path(directory)
            (package / "Makefile").write_text("PKG_NAME:=miniupnpd\n", encoding="utf-8")
            result = run_script(package)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PKG_VERSION", result.stderr)

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
        self.assertIn("miniupnpd/ci-source.txt ./upload/MINIUPNPD-SOURCE.txt", workflow)

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
