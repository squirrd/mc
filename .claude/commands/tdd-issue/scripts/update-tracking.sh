#!/usr/bin/env bash
# update-tracking.sh — Read-then-write updates to ISSUE_TRACKING.md
#
# Uses Python for structured markdown manipulation (bash is unsuitable for this).
#
# Usage:
#   update-tracking.sh --action add-issue       --issue <branch> --description <text> --severity <s> --source <src>
#   update-tracking.sh --action add-integration-test --issue <branch> --test-function <fn> --test-file <file> --status <RED|GREEN>
#   update-tracking.sh --action update-integration-test --issue <branch> --test-function <fn> --status <RED|GREEN>
#   update-tracking.sh --action add-unit-test   --issue <branch> --unit-test <name> --src-file <file> --branch <branch> --status <RED|GREEN|MERGED>
#   update-tracking.sh --action update-unit-test --issue <branch> --unit-test <name> --status <RED|GREEN|MERGED>
#   update-tracking.sh --action close-issue     --issue <branch>

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
TRACKING_FILE="$REPO_ROOT/.tdd/issues/ISSUE_TRACKING.md"

if [[ ! -f "$TRACKING_FILE" ]]; then
    echo "ERROR: Tracking file not found: $TRACKING_FILE" >&2
    echo "Run bootstrap.sh first." >&2
    exit 1
fi

# Pass all arguments to the Python updater
python3 - "$TRACKING_FILE" "$@" <<'PYTHON'
import sys
import re
import os
from datetime import datetime, date

def now_timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def today():
    return date.today().strftime("%Y-%m-%d")

def parse_args(args):
    d = {}
    i = 0
    while i < len(args):
        if args[i].startswith("--"):
            key = args[i].lstrip("-")
            if i + 1 < len(args) and not args[i+1].startswith("--"):
                d[key] = args[i+1]
                i += 2
            else:
                d[key] = True
                i += 1
        else:
            i += 1
    return d

def read_file(path):
    with open(path, "r") as f:
        return f.read()

def write_file(path, content):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(content)
    os.replace(tmp, path)

def update_last_modified(content):
    return re.sub(
        r"(Last updated:).*",
        f"Last updated: {now_timestamp()}",
        content,
        count=1,
    )

def add_issue(content, issue, description, severity, source):
    # Build new issue section
    worktree = f".tdd/worktrees/{issue}"
    new_section = f"""
### {issue}

| Field       | Value                                           |
|-------------|-------------------------------------------------|
| Status      | IN_PROGRESS                                     |
| Created     | {today()}                                       |
| Description | {description}                                   |
| Branch      | {issue}                                         |
| Worktree    | {worktree}                                      |
| Source      | {source}                                        |
| Severity    | {severity}                                      |

#### Integration Tests

| Test Function | File | Status | Notes |
|---|---|---|---|
| (none yet) | | | |

#### Unit Tests

| Test Function | Src File | Branch | Worktree | Status |
|---|---|---|---|---|
| (none yet) | | | | |

---
"""
    # Insert before "## Completed Issues" or at end of Active Issues section
    if "## Completed Issues" in content:
        content = content.replace("## Completed Issues", new_section + "\n## Completed Issues", 1)
    else:
        content += new_section

    # Remove placeholder "(none)" in Active Issues if it exists
    content = re.sub(r"\(none\)\s*\n\n---\n\n## Active Issues\n", "", content)
    return content

def add_integration_test(content, issue, test_function, test_file, status):
    row = f"| {test_function} | {test_file} | {status} | Added {today()} |"
    placeholder_pattern = rf"(### {re.escape(issue)}.*?#### Integration Tests\n\n\|.*?\|\n\|.*?\|\n)\| \(none yet\).*?\n"

    def replace_placeholder(m):
        return m.group(1) + row + "\n"

    new_content = re.sub(placeholder_pattern, replace_placeholder, content, flags=re.DOTALL)
    if new_content == content:
        # Append to integration tests table for this issue
        pattern = rf"(### {re.escape(issue)}.*?#### Integration Tests\n\n\|.*?\|\n\|.*?\|\n)(.*?)(\n#### Unit Tests)"
        def append_row(m):
            return m.group(1) + m.group(2) + row + "\n" + m.group(3)
        content = re.sub(pattern, append_row, content, flags=re.DOTALL)
    else:
        content = new_content
    return content

def update_integration_test(content, issue, test_function, status):
    # Find the row for this test function and update its status column
    def replace_status(m):
        row = m.group(0)
        # Replace the status column (3rd pipe-delimited field)
        parts = row.split("|")
        if len(parts) >= 4:
            parts[3] = f" {status} "
            return "|".join(parts)
        return row

    pattern = rf"\| {re.escape(test_function)} \|[^\n]+"
    content = re.sub(pattern, replace_status, content)
    return content

def add_unit_test(content, issue, unit_test, src_file, branch, status):
    worktree = f".tdd/worktrees/{branch}"
    test_fn = unit_test.replace("-", "_")
    row = f"| {test_fn} | {src_file} | {branch} | {worktree} | {status} |"
    placeholder_pattern = rf"(### {re.escape(issue)}.*?#### Unit Tests\n\n\|.*?\|\n\|.*?\|\n)\| \(none yet\).*?\n"

    def replace_placeholder(m):
        return m.group(1) + row + "\n"

    new_content = re.sub(placeholder_pattern, replace_placeholder, content, flags=re.DOTALL)
    if new_content == content:
        # Append to unit tests table for this issue
        pattern = rf"(### {re.escape(issue)}.*?#### Unit Tests\n\n\|.*?\|\n\|.*?\|\n)(.*?)(\n\n---)"
        def append_row(m):
            return m.group(1) + m.group(2) + row + "\n" + m.group(3)
        content = re.sub(pattern, append_row, content, flags=re.DOTALL)
    else:
        content = new_content
    return content

def update_unit_test(content, issue, unit_test, status):
    test_fn = unit_test.replace("-", "_")

    def replace_status(m):
        row = m.group(0)
        parts = row.split("|")
        if len(parts) >= 6:
            parts[5] = f" {status} "
            return "|".join(parts)
        return row

    pattern = rf"\| {re.escape(test_fn)} \|[^\n]+"
    content = re.sub(pattern, replace_status, content)
    return content

def close_issue(content, issue):
    # Extract the issue section from Active Issues
    pattern = rf"(### {re.escape(issue)}\n.*?---\n)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        print(f"WARNING: Issue {issue} not found in Active Issues — may already be closed.", file=sys.stderr)
        return content

    issue_block = match.group(1)

    # Update Status to DONE and add Completed date
    issue_block = re.sub(r"\| Status\s+\| IN_PROGRESS\s+\|", f"| Status      | DONE                                            |", issue_block)
    issue_block = re.sub(r"\| Created\s+\| (\S+)\s+\|", lambda m: m.group(0).rstrip() + f"\n| Completed   | {today()}                                       |", issue_block, count=1)
    issue_block = re.sub(r"\| Worktree\s+\|[^\|]+\|", f"| Merged into | main                                            |", issue_block)

    # Remove from Active Issues
    content = content.replace(match.group(1), "", 1)

    # Append to Completed Issues
    completed_section = "## Completed Issues"
    if completed_section in content:
        content = content.replace(
            completed_section,
            completed_section + "\n" + issue_block,
            1,
        )
    else:
        content += "\n## Completed Issues\n\n" + issue_block

    # Clean up empty Active Issues placeholder
    content = re.sub(r"## Active Issues\n\n---\n", "## Active Issues\n\n(none)\n\n---\n", content)
    return content

# --- Main ---
tracking_file = sys.argv[1]
args = parse_args(sys.argv[2:])
action = args.get("action", "")

content = read_file(tracking_file)

if action == "add-issue":
    content = add_issue(
        content,
        issue=args["issue"],
        description=args.get("description", ""),
        severity=args.get("severity", "major"),
        source=args.get("source", "ad-hoc"),
    )
elif action == "add-integration-test":
    content = add_integration_test(
        content,
        issue=args["issue"],
        test_function=args["test-function"],
        test_file=args["test-file"],
        status=args.get("status", "RED"),
    )
elif action == "update-integration-test":
    content = update_integration_test(
        content,
        issue=args["issue"],
        test_function=args["test-function"],
        status=args["status"],
    )
elif action == "add-unit-test":
    content = add_unit_test(
        content,
        issue=args["issue"],
        unit_test=args["unit-test"],
        src_file=args["src-file"],
        branch=args["branch"],
        status=args.get("status", "RED"),
    )
elif action == "update-unit-test":
    content = update_unit_test(
        content,
        issue=args["issue"],
        unit_test=args["unit-test"],
        status=args["status"],
    )
elif action == "close-issue":
    content = close_issue(content, issue=args["issue"])
else:
    print(f"ERROR: Unknown action '{action}'", file=sys.stderr)
    print("Valid actions: add-issue, add-integration-test, update-integration-test,", file=sys.stderr)
    print("               add-unit-test, update-unit-test, close-issue", file=sys.stderr)
    sys.exit(1)

content = update_last_modified(content)
write_file(tracking_file, content)
print(f"Updated: {tracking_file} (action: {action})")
PYTHON
