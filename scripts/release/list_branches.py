#!/usr/bin/env python3
"""List branches available for release, sorted oldest → newest by last commit.

Fetches from remote first, then lists all branches excluding:
  - main
  - HEAD
  - version branches (matching v[0-9]+.*)

Usage:
    python scripts/release/list_branches.py [--exclude v2.0.9]

Outputs a numbered list for display, or --json for machine-readable output.
"""

import json
import re
import subprocess
import sys
from typing import Optional


def fetch_remote() -> None:
    subprocess.run(["git", "fetch", "--prune"], capture_output=True)


def is_excluded(name: str, extra_exclude: Optional[str] = None) -> bool:
    if name in ("HEAD", "main", "origin"):
        return True
    # Skip remote-tracking pointers like "HEAD -> origin/main"
    if "->" in name:
        return True
    if re.match(r"^v\d+", name):
        return True
    if extra_exclude and name == extra_exclude:
        return True
    return False


def get_branches(extra_exclude: Optional[str] = None) -> list[dict]:
    # Remote branches (authoritative, includes team members' work)
    remote_result = subprocess.run(
        [
            "git",
            "branch",
            "-r",
            "--sort=committerdate",
            "--format=%(refname:short)\t%(committerdate:iso8601)\t%(objectname:short)",
        ],
        capture_output=True,
        text=True,
    )

    seen: set[str] = set()
    branches: list[dict] = []

    for line in remote_result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        refname = parts[0].strip()
        date = parts[1].strip() if len(parts) > 1 else ""
        sha = parts[2].strip() if len(parts) > 2 else ""

        # Strip origin/ prefix
        name = refname.removeprefix("origin/")
        if is_excluded(name, extra_exclude):
            continue

        seen.add(name)
        branches.append(
            {
                "name": name,
                "remote": refname,
                "date": date,
                "sha": sha,
                "local_only": False,
            }
        )

    # Local-only branches (not yet pushed)
    local_result = subprocess.run(
        [
            "git",
            "branch",
            "--sort=committerdate",
            "--format=%(refname:short)\t%(committerdate:iso8601)\t%(objectname:short)",
        ],
        capture_output=True,
        text=True,
    )

    for line in local_result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        date = parts[1].strip() if len(parts) > 1 else ""
        sha = parts[2].strip() if len(parts) > 2 else ""

        if is_excluded(name, extra_exclude):
            continue
        if name in seen:
            continue

        branches.append(
            {
                "name": name,
                "remote": None,
                "date": date,
                "sha": sha,
                "local_only": True,
            }
        )

    # Re-sort by date (mixing remote + local)
    branches.sort(key=lambda x: x["date"])
    return branches


def main() -> None:
    extra_exclude: Optional[str] = None
    use_json = "--json" in sys.argv

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--exclude" and i < len(sys.argv) - 1:
            extra_exclude = sys.argv[i + 1]

    fetch_remote()
    branches = get_branches(extra_exclude)

    if use_json:
        print(json.dumps(branches, indent=2))
        return

    if not branches:
        print("No branches available for release.")
        return

    print(f"\n{'#':>3}  {'Branch':<45}  {'Last Updated':<12}  {'Location'}")
    print(f"{'---':>3}  {'-'*45}  {'-'*12}  {'-'*10}")
    for i, b in enumerate(branches, 1):
        location = "[local only]" if b["local_only"] else "remote"
        date_str = b["date"][:10] if b["date"] else "unknown"
        print(f"{i:>3}.  {b['name']:<45}  {date_str:<12}  {location}")
    print()


if __name__ == "__main__":
    main()
