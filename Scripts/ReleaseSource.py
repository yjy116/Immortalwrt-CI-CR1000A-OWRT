#!/usr/bin/env python3
"""Resolve formal proxy releases once, then check out their exact commits."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen


PROVIDERS = {"daede": "kenzok8/openwrt-daede", "honk": "kenzok8/openwrt-honk"}
API_ROOT = "https://api.github.com/"
API_TIMEOUT_SECONDS = 30
COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
RELEASE_PATTERN = re.compile(r"v[0-9][A-Za-z0-9._+-]*")


def fetch_json(path):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "CR1000A-CI"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(API_ROOT + path, headers=headers)
    with urlopen(request, timeout=API_TIMEOUT_SECONDS) as response:
        return json.load(response)


def validate_release_fields(repository, value):
    tag = value["tag"]
    if not isinstance(tag, str) or not RELEASE_PATTERN.fullmatch(tag):
        raise ValueError("Expected a formal v* release tag, not a source/candidate tag")
    if type(value["release_id"]) is not int or value["release_id"] <= 0:
        raise ValueError("Invalid release ID")
    published = value["published_at"]
    if not isinstance(published, str) or not published.endswith("Z"):
        raise ValueError("Missing release publication timestamp")
    datetime.fromisoformat(published.replace("Z", "+00:00"))
    if value["url"] != f"https://github.com/{repository}/releases/tag/{tag}":
        raise ValueError("Release URL does not match its provider and tag")


def resolve_commit(repository, target, fetch):
    seen = set()
    while True:
        sha = target["sha"]
        if not isinstance(sha, str) or not COMMIT_PATTERN.fullmatch(sha):
            raise ValueError("Invalid release commit SHA")
        if target["type"] == "commit":
            return sha
        if target["type"] != "tag" or sha in seen:
            raise ValueError("Release tag does not resolve to a commit")
        seen.add(sha)
        target = fetch(f"repos/{repository}/git/tags/{sha}")["object"]


def resolve_release(repository, fetch):
    release = fetch(f"repos/{repository}/releases/latest")
    if release["draft"] is not False or release["prerelease"] is not False:
        raise ValueError("Latest release is a draft or prerelease")
    selected = {
        "repository": repository, "tag": release["tag_name"],
        "release_id": release["id"], "published_at": release["published_at"],
        "url": release["html_url"],
    }
    validate_release_fields(repository, selected)
    tag = selected["tag"]
    ref = fetch(f"repos/{repository}/git/ref/tags/{quote(tag, safe='')}")
    if ref["ref"] != f"refs/tags/{tag}":
        raise ValueError("Git tag response does not match the release")
    commit = resolve_commit(repository, ref["object"], fetch)
    return {**selected, "commit": commit}


def validate_selection(package, selected):
    if selected["repository"] != PROVIDERS[package]:
        raise ValueError("Unexpected package provider")
    validate_release_fields(PROVIDERS[package], selected)
    commit = selected["commit"]
    if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
        raise ValueError("Expected an exact release commit SHA")


def checkout(package, destination, selections):
    selected = selections[package]
    validate_selection(package, selected)
    destination = Path(destination)
    repository = f"https://github.com/{selected['repository']}.git"
    commit = selected["commit"]
    subprocess.run(["git", "init", str(destination)], check=True)
    command = ["git", "-C", str(destination)]
    subprocess.run([*command, "fetch", "--depth=1", repository, commit], check=True)
    subprocess.run([*command, "-c", "core.autocrlf=false", "checkout", "--detach", "FETCH_HEAD"],
                   check=True)
    actual = subprocess.run([*command, "rev-parse", "HEAD"], check=True,
                            text=True, capture_output=True).stdout.strip()
    if actual != commit:
        raise ValueError("Checked-out commit differs from the selected release commit")
    record = {
        "PACKAGING_REPO": repository, "PACKAGING_COMMIT": actual,
        "PACKAGING_TAG": selected["tag"], "PACKAGING_RELEASE_ID": selected["release_id"],
        "PACKAGING_RELEASE_URL": selected["url"], "PACKAGING_PUBLISHED_AT": selected["published_at"],
    }
    path = destination / "ci/RELEASE-SOURCE.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{key}={value}\n" for key, value in record.items()), encoding="utf-8")
    print(f"Selected {package}: {selected['tag']} ({actual})")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("resolve")
    source = actions.add_parser("checkout")
    source.add_argument("package", choices=PROVIDERS)
    source.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    if arguments.action == "resolve":
        releases = {key: resolve_release(repo, fetch_json) for key, repo in PROVIDERS.items()}
        print(json.dumps(releases, separators=(",", ":")))
    else:
        selections = json.loads(os.environ["WRT_PROXY_RELEASES"])
        checkout(arguments.package, arguments.destination, selections)


if __name__ == "__main__":
    main()
