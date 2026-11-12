"""Select the stable channel even when GitHub latest points at linux66."""

import importlib.util
import unittest
from unittest.mock import patch

from test_release_source import COMMIT, PROVIDER, SCRIPT, TAG, release_fixture


PAGE_SIZE = 2
BASE = f"repos/{PROVIDER}"
LINUX66 = {**release_fixture(), "tag_name": "linux66-2026.11.09.1"}


def load_resolver():
    spec = importlib.util.spec_from_file_location("release_channels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_pages(pages):
    module = load_resolver()
    responses = {f"{BASE}/releases/latest": LINUX66}
    responses.update({f"{BASE}/releases?per_page={PAGE_SIZE}&page={index}": page
                      for index, page in enumerate(pages, start=1)})
    responses[f"{BASE}/git/ref/tags/{TAG}"] = {
        "ref": f"refs/tags/{TAG}", "object": {"type": "commit", "sha": COMMIT},
    }
    with patch.object(module, "RELEASE_PAGE_SIZE", PAGE_SIZE, create=True):
        return module.resolve_release(PROVIDER, responses.__getitem__)


class ReleaseChannelTests(unittest.TestCase):
    def test_linux66_latest_does_not_hide_stable_release(self):
        selected = resolve_pages([[LINUX66, release_fixture()], []])
        self.assertEqual(TAG, selected["tag"])
        self.assertEqual(COMMIT, selected["commit"])

    def test_pagination_finds_stable_release_after_experimental_page(self):
        source = {**release_fixture(), "tag_name": "source-123", "prerelease": True}
        selected = resolve_pages([[LINUX66, source], [release_fixture()]])
        self.assertEqual(TAG, selected["tag"])

    def test_publication_date_wins_over_list_order_across_pages(self):
        older = {**release_fixture(), "tag_name": "v2026.10.20",
                 "html_url": f"https://github.com/{PROVIDER}/releases/tag/v2026.10.20",
                 "published_at": "2026-10-20T13:38:23Z"}
        selected = resolve_pages([[older, LINUX66], [release_fixture()]])
        self.assertEqual(TAG, selected["tag"])

    def test_drafts_and_prereleases_do_not_replace_stable_release(self):
        newer = {**release_fixture(), "published_at": "2026-11-12T00:00:00Z"}
        pages = [[{**newer, "draft": True}, {**newer, "prerelease": True}],
                 [release_fixture()]]
        self.assertEqual(TAG, resolve_pages(pages)["tag"])

    def test_no_formal_release_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "No published formal.*kenzok8"):
            resolve_pages([[LINUX66]])

    def test_invalid_formal_metadata_is_not_silently_downgraded(self):
        malformed = {**release_fixture(), "published_at": "invalid"}
        with self.assertRaisesRegex(ValueError, "timestamp"):
            resolve_pages([[release_fixture(), malformed], []])

    def test_later_page_api_failure_is_not_hidden_by_first_page_release(self):
        module = load_resolver()

        def fetch(path):
            if path.endswith("/releases/latest"):
                return LINUX66
            if path.endswith("page=1"):
                return [release_fixture(), LINUX66]
            raise RuntimeError("release API unavailable")

        with patch.object(module, "RELEASE_PAGE_SIZE", PAGE_SIZE, create=True):
            with self.assertRaisesRegex(RuntimeError, "release API unavailable"):
                module.resolve_release(PROVIDER, fetch)


if __name__ == "__main__":
    unittest.main()
