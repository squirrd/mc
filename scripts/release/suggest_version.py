#!/usr/bin/env python3
"""Suggest the next release version based on existing git tags.

Usage:
    python scripts/release/suggest_version.py [patch|minor|major]
    python scripts/release/suggest_version.py minor-bump
    python scripts/release/suggest_version.py major-bump

Prints the suggested version string (no 'v' prefix).
"""

import re
import subprocess
import sys


def main() -> None:
    bump_type = "patch"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if "major" in arg:
            bump_type = "major"
        elif "minor" in arg:
            bump_type = "minor"

    result = subprocess.run(
        ["git", "tag", "--list", "v*", "--sort=-version:refname"],
        capture_output=True,
        text=True,
    )

    tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
    semver_tags = [t for t in tags if re.match(r"^v\d+\.\d+\.\d+$", t)]

    if not semver_tags:
        print("0.1.0")
        return

    latest = semver_tags[0].lstrip("v")
    parts = latest.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    else:
        patch += 1

    print(f"{major}.{minor}.{patch}")


if __name__ == "__main__":
    main()
