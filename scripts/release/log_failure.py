#!/usr/bin/env python3
"""Log a branch merge failure to .planning/release-log.md.

Usage:
    python scripts/release/log_failure.py <version> <branch> [reason]
"""

import sys
from datetime import datetime, timezone
from pathlib import Path


HEADER = """# Release Log

Tracks branches that failed the test suite during release builds.

| Date (UTC) | Version | Branch | Status | Notes |
|------------|---------|--------|--------|-------|
"""


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: log_failure.py <version> <branch> [reason]", file=sys.stderr)
        sys.exit(1)

    version = sys.argv[1]
    branch = sys.argv[2]
    reason = sys.argv[3] if len(sys.argv) > 3 else "Test suite failed after merge"

    log_path = Path(".planning/release-log.md")
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = f"| {timestamp} | {version} | `{branch}` | ❌ Failed | {reason} |\n"

    if not log_path.exists():
        log_path.write_text(HEADER + entry)
    else:
        content = log_path.read_text()
        # Insert after header table if it exists, otherwise append
        if "| Date" in content:
            log_path.write_text(content + entry)
        else:
            log_path.write_text(HEADER + entry)

    print(f"Logged: {branch} failed in v{version} → {log_path}")


if __name__ == "__main__":
    main()
