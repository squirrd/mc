#!/usr/bin/env python3
"""
Analyze git commits since a given date, map changed files to UAT features.

Usage:
    python scripts/uat/analyze_git.py --since YYYY-MM-DD [--feature FEATURE]

Output (stdout): JSON mapping of {feature: [commit_summaries]}
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
FEATURE_MAP_FILE = ROOT / "tests/uat/data/feature_map.json"


def load_feature_map() -> dict[str, Any]:
    return json.loads(FEATURE_MAP_FILE.read_text())


def git_log_since(since: str) -> list[dict[str, Any]]:
    """Return list of commits since date with changed files."""
    # Get commit list: hash|subject
    result = subprocess.run(
        ["git", "log", f"--since={since}", "--format=%H|%s", "--no-merges"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    commits = []
    for line in result.stdout.strip().splitlines():
        if "|" not in line:
            continue
        commit_hash, subject = line.split("|", 1)

        # Get changed files for this commit
        files_result = subprocess.run(
            ["git", "show", "--name-only", "--format=", commit_hash],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        changed_files = [
            f.strip() for f in files_result.stdout.strip().splitlines() if f.strip()
        ]
        commits.append(
            {"hash": commit_hash[:8], "subject": subject.strip(), "files": changed_files}
        )

    return commits


def map_commits_to_features(
    commits: list[dict[str, Any]], feature_map: dict[str, Any]
) -> dict[str, list[dict[str, Any]]]:
    """For each feature, collect commits that touched its source paths."""
    # Build a flat {path_prefix: feature_key} lookup across both binaries
    path_to_features: dict[str, list[str]] = {}
    for _binary, features in feature_map.items():
        for feature_key, meta in features.items():
            for src_path in meta.get("source_paths", []):
                path_to_features.setdefault(src_path, []).append(feature_key)

    result: dict[str, list[dict[str, Any]]] = {}

    for commit in commits:
        matched_features: set[str] = set()
        for changed_file in commit["files"]:
            for src_path, feature_keys in path_to_features.items():
                if changed_file.startswith(src_path) or changed_file == src_path:
                    matched_features.update(feature_keys)

        for feature_key in matched_features:
            result.setdefault(feature_key, []).append(
                {"hash": commit["hash"], "subject": commit["subject"]}
            )

    return result


def main() -> None:
    since = None
    feature_filter = None

    if "--since" in sys.argv:
        idx = sys.argv.index("--since")
        if idx + 1 < len(sys.argv):
            since = sys.argv[idx + 1]

    if "--feature" in sys.argv:
        idx = sys.argv.index("--feature")
        if idx + 1 < len(sys.argv):
            feature_filter = sys.argv[idx + 1]

    if not since:
        print("Error: --since YYYY-MM-DD is required", file=sys.stderr)
        sys.exit(1)

    feature_map = load_feature_map()
    commits = git_log_since(since)

    if not commits:
        print(json.dumps({}))
        return

    feature_commits = map_commits_to_features(commits, feature_map)

    if feature_filter:
        feature_commits = {k: v for k, v in feature_commits.items() if k == feature_filter}

    print(json.dumps(feature_commits, indent=2))


if __name__ == "__main__":
    main()
