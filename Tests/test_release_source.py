"""Exercise formal-release resolution and immutable source checkout."""

import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import yaml


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "Scripts/ReleaseSource.py"
COMMIT = "a" * 40
TAG_OBJECT = "b" * 40
PROVIDER = "kenzok8/openwrt-daede"
TAG = "v2026.10.30-example"
TIMEOUT = 60


def release_fixture():
    return {
        "id": 42, "tag_name": TAG, "target_commitish": "main",
        "draft": False, "prerelease": False,
        "published_at": "2026-10-31T13:38:23Z",
        "html_url": f"https://github.com/{PROVIDER}/releases/tag/{TAG}",
    }


def selection_fixture(commit=COMMIT):
    return {
        "repository": PROVIDER, "tag": TAG, "commit": commit,
        "release_id": 42, "published_at": "2026-10-31T13:38:23Z",
        "url": f"https://github.com/{PROVIDER}/releases/tag/{TAG}",
    }


class ReleaseSourceTests(unittest.TestCase):
    def load(self):
        self.assertTrue(SCRIPT.is_file(), "Formal release resolver is missing")
        spec = importlib.util.spec_from_file_location("release_source", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def resolve(self, module, *, release=None, annotated=False):
        base = f"repos/{PROVIDER}"
        responses = {
            f"{base}/releases?per_page={module.RELEASE_PAGE_SIZE}&page=1":
                [release or release_fixture()],
            f"{base}/git/ref/tags/{TAG}": {
                "ref": f"refs/tags/{TAG}",
                "object": {"type": "tag" if annotated else "commit",
                           "sha": TAG_OBJECT if annotated else COMMIT},
            },
            f"{base}/git/tags/{TAG_OBJECT}": {"object": {"type": "commit", "sha": COMMIT}},
        }
        return module.resolve_release(PROVIDER, responses.__getitem__)

    def test_lightweight_tag_resolves_commit_not_target_branch(self):
        self.assertEqual(selection_fixture(), self.resolve(self.load()))

    def test_annotated_tag_resolves_to_commit_not_tag_object(self):
        self.assertEqual(COMMIT, self.resolve(self.load(), annotated=True)["commit"])

    def test_nonformal_or_malformed_release_is_rejected(self):
        module = self.load()
        changes = ({"draft": True}, {"prerelease": True}, {"draft": None},
                   {"tag_name": "daed-src"}, {"tag_name": "candidate-r123"},
                   {"tag_name": "v1\ninjected=value"}, {"id": "42"},
                   {"published_at": None}, {"published_at": "invalid"},
                   {"html_url": "https://example.invalid/release"})
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.resolve(module, release={**release_fixture(), **change})

    def test_api_failure_is_exposed_without_branch_fallback(self):
        module = self.load()
        with self.assertRaisesRegex(RuntimeError, "rate limited"):
            module.resolve_release(PROVIDER, lambda _: (_ for _ in ()).throw(
                RuntimeError("rate limited")))

    def test_invalid_tag_target_and_cycles_are_rejected(self):
        module = self.load()
        for target in ({"type": "tree", "sha": COMMIT},
                       {"type": "commit", "sha": "main"},
                       {"type": "tag", "sha": TAG_OBJECT}):
            def fetch(path):
                if "/releases?" in path:
                    return [release_fixture()]
                return {"ref": f"refs/tags/{TAG}", "object": target}
            with self.subTest(target=target), self.assertRaises(ValueError):
                module.resolve_release(PROVIDER, fetch)

    def test_selection_rejects_wrong_provider_and_bad_sha(self):
        module = self.load()
        for change in ({"repository": "attacker/repository"}, {"commit": "main"},
                       {"tag": "source-123"}, {"commit": "a" * 40 + "\n"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                module.validate_selection("daede", {**selection_fixture(), **change})

    def test_checkout_keeps_release_commit_when_main_has_advanced(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            upstream = root / "upstream"
            upstream.mkdir()
            git(upstream, "init", "--quiet")
            git(upstream, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--allow-empty", "-qm", "Release")
            released = git(upstream, "rev-parse", "HEAD").strip()
            git(upstream, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                "commit", "--allow-empty", "-qm", "Unreleased change")
            destination = root / "prepared"
            selection = selection_fixture(released)
            # Redirect only Git's network transport; checkout and SHA checks remain real.
            environment = {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": f"url.{upstream.as_uri()}.insteadOf",
                "GIT_CONFIG_VALUE_0": f"https://github.com/{PROVIDER}.git",
            }
            with patch.dict(os.environ, environment):
                module.checkout("daede", destination, {"daede": selection})
            self.assertEqual(released, git(destination, "rev-parse", "HEAD").strip())
            record = (destination / "ci/RELEASE-SOURCE.txt").read_text()
            self.assertIn(f"PACKAGING_COMMIT={released}\n", record)
            self.assertIn(f"PACKAGING_TAG={TAG}\n", record)
            self.assertIn("PACKAGING_RELEASE_ID=42\n", record)

    def test_checkout_mismatch_does_not_write_success_record(self):
        module = self.load()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = subprocess.CompletedProcess([], 0, stdout="c" * 40 + "\n")
            with patch.object(module.subprocess, "run", return_value=result):
                with self.assertRaisesRegex(ValueError, "commit"):
                    module.checkout("daede", root, {"daede": selection_fixture()})
            self.assertFalse((root / "ci/RELEASE-SOURCE.txt").exists())


def git(directory, *arguments):
    return subprocess.run(["git", "-C", str(directory), *arguments], check=True,
                          text=True, capture_output=True, timeout=TIMEOUT).stdout


class ReleaseWorkflowTests(unittest.TestCase):
    def test_both_matrices_consume_one_shared_release_resolution(self):
        for name in ("CR1000A.yml", "CR1000A-TEST.yml"):
            workflow = yaml.safe_load((REPO / ".github/workflows" / name).read_text(encoding="utf-8"))
            jobs = workflow["jobs"]
            with self.subTest(name=name):
                self.assertIn("proxy-releases", jobs, "Release lookup must precede both variants")
                self.assertEqual("./.github/workflows/PROXY-RELEASES.yml",
                                 jobs["proxy-releases"]["uses"])
                self.assertEqual("proxy-releases", jobs["config"]["needs"])
                self.assertEqual("${{needs.proxy-releases.outputs.releases}}",
                                 jobs["config"]["with"]["WRT_PROXY_RELEASES"])

    def test_resolution_is_passed_to_package_scripts(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/WRT-CORE.yml").read_text(encoding="utf-8"))
        self.assertEqual("${{inputs.WRT_PROXY_RELEASES}}", workflow["env"].get("WRT_PROXY_RELEASES"))
        self.assertTrue(workflow[True]["workflow_call"]["inputs"]["WRT_PROXY_RELEASES"]["required"])


if __name__ == "__main__":
    unittest.main()
