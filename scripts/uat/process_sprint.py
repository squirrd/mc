#!/usr/bin/env python3
"""
Process a completed UAT sprint file.

1. Parse pass/fail/blocked results from checkboxes
2. Update tests/uat/data/tc_history.json
3. Update tests/uat/STATUS.md
4. Print failed TCs in Jira-format (to stdout)
5. Move sprint file from runs/pending/ to runs/completed/

Usage:
    python scripts/uat/process_sprint.py [--sprint YYYY-MM-DD] [--dry-run]

If --sprint is not given, uses the most recent pending sprint.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
PENDING_DIR = ROOT / "tests/uat/runs/pending"
COMPLETED_DIR = ROOT / "tests/uat/runs/completed"
HISTORY_FILE = ROOT / "tests/uat/data/tc_history.json"
STATUS_FILE = ROOT / "tests/uat/STATUS.md"
FEATURES_DIR = ROOT / "tests/uat/features"
FEATURE_MAP_FILE = ROOT / "tests/uat/data/feature_map.json"

TC_SECTION_RE = re.compile(r"^### (TC-[A-Z]+-\d+): (.+)$", re.MULTILINE)
RESULT_RE = re.compile(r"- \[x\] (PASS|FAIL|BLOCKED)", re.IGNORECASE)
NOTES_RE = re.compile(r"\*\*Notes:\*\*\s*(.+?)(?=\n(?:###|---|\Z))", re.DOTALL)


def find_pending_sprint(sprint_date: str | None) -> Path:
    if sprint_date:
        path = PENDING_DIR / f"{sprint_date}.md"
        if not path.exists():
            print(f"Error: Sprint file not found: {path}", file=sys.stderr)
            sys.exit(1)
        return path

    pending = sorted(PENDING_DIR.glob("*.md"), reverse=True)
    if not pending:
        print("Error: No pending sprint files found.", file=sys.stderr)
        sys.exit(1)
    return pending[0]


def parse_sprint_file(path: Path) -> tuple[str, list[dict[str, Any]]]:
    """Parse sprint markdown, return (sprint_date, list of TC results)."""
    content = path.read_text()
    sprint_date = path.stem

    results: list[dict[str, Any]] = []
    sections = list(TC_SECTION_RE.finditer(content))

    for i, match in enumerate(sections):
        tc_id = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = sections[i + 1].start() if i + 1 < len(sections) else len(content)
        block = content[start:end]

        result_match = RESULT_RE.search(block)
        result = result_match.group(1).upper() if result_match else None

        notes_match = NOTES_RE.search(block)
        notes = ""
        if notes_match:
            raw = notes_match.group(1).strip()
            # Strip HTML comment placeholder
            if not raw.startswith("<!--") and raw:
                notes = raw

        results.append(
            {
                "id": tc_id,
                "title": title,
                "result": result,
                "notes": notes,
                "date": sprint_date,
            }
        )

    return sprint_date, results


def update_history(sprint_date: str, results: list[dict[str, Any]]) -> None:
    data: dict[str, Any] = {"_schema": "1.0", "_comment": "Managed by process_sprint.py", "tcs": {}}
    if HISTORY_FILE.exists():
        data = json.loads(HISTORY_FILE.read_text())

    tcs = data.setdefault("tcs", {})

    for r in results:
        if not r["result"]:
            continue  # Skipped TC — don't record
        tc_id = r["id"]
        entry = tcs.setdefault(tc_id, {"run_count": 0, "history": []})
        entry["last_run"] = r["date"]
        entry["last_result"] = r["result"]
        entry["run_count"] = entry.get("run_count", 0) + 1
        entry["history"].append(
            {"date": r["date"], "result": r["result"], "notes": r["notes"]}
        )

    HISTORY_FILE.write_text(json.dumps(data, indent=2))


def build_jira_output(sprint_date: str, results: list[dict[str, Any]]) -> str:
    failures = [r for r in results if r["result"] in ("FAIL", "BLOCKED")]
    if not failures:
        return f"Sprint {sprint_date}: All tests passed. No Jira issues to file.\n"

    lines = [
        f"FAILED / BLOCKED TESTS — Sprint {sprint_date}",
        "=" * 50,
        "",
    ]

    for r in failures:
        tc_id = r["id"]
        # Derive feature prefix from TC ID: TC-UPIN-01 → UPIN
        prefix = tc_id.rsplit("-", 1)[0].lstrip("TC-")
        lines += [
            f"[{r['result']}] {tc_id}: {r['title']}",
            f"  Prefix : {prefix}",
            f"  Date   : {r['date']}",
        ]
        if r["notes"]:
            lines.append(f"  Notes  : {r['notes']}")
        lines.append("")

    lines += [
        "--- Suggested Jira summary format ---",
        "",
    ]
    for r in failures:
        lines.append(
            f"  [UAT-{sprint_date}] {r['id']}: {r['title']} — {r.get('notes', 'see sprint results')}"
        )
    lines.append("")

    return "\n".join(lines)


def count_all_tcs_per_feature() -> dict[str, int]:
    """Count TCs per feature from feature files."""
    from scripts.uat import parse_features  # type: ignore[import]

    counts: dict[str, int] = {}
    for path in sorted(FEATURES_DIR.glob("*.md")):
        feature = path.stem
        try:
            tcs = parse_features.parse_feature_file(path)
            counts[feature] = len(tcs)
        except Exception:
            counts[feature] = 0
    return counts


def update_status_md(
    sprint_date: str,
    results: list[dict[str, Any]],
    history_file: Path,
) -> None:
    """Rewrite STATUS.md with updated stats from full history."""
    if not HISTORY_FILE.exists():
        return

    history_data = json.loads(HISTORY_FILE.read_text())
    tcs = history_data.get("tcs", {})

    feature_map_data = json.loads(FEATURE_MAP_FILE.read_text())

    # Build feature → TC counts from feature files
    tc_counts: dict[str, int] = {}
    for path in sorted(FEATURES_DIR.glob("*.md")):
        feature = path.stem
        content = path.read_text()
        count = len(re.findall(r"^### TC-[A-Z]+-\d+:", content, re.MULTILINE))
        tc_counts[feature] = count

    # Compute per-feature stats from history
    feature_stats: dict[str, dict[str, Any]] = {}
    for tc_id, tc_hist in tcs.items():
        # Derive feature from prefix
        prefix = tc_id.rsplit("-", 1)[0].lstrip("TC-")
        feature = _prefix_to_feature(prefix, feature_map_data)
        if not feature:
            continue
        stats = feature_stats.setdefault(feature, {"last_sprint": None, "pass": 0, "fail": 0, "blocked": 0})
        run_date = tc_hist.get("last_run")
        if run_date and (stats["last_sprint"] is None or run_date > stats["last_sprint"]):
            stats["last_sprint"] = run_date
        result = tc_hist.get("last_result", "")
        if result == "PASS":
            stats["pass"] += 1
        elif result == "FAIL":
            stats["fail"] += 1
        elif result == "BLOCKED":
            stats["blocked"] += 1

    # Collect sprint history from completed dir
    sprint_rows: list[str] = []
    for completed in sorted(COMPLETED_DIR.glob("*.md"), reverse=True):
        sprint_d = completed.stem
        content = completed.read_text()
        sprint_results = list(TC_SECTION_RE.finditer(content))
        n_selected = len(sprint_results)
        n_pass = content.count("[x] PASS")
        n_fail = content.count("[x] FAIL")
        n_blocked = content.count("[x] BLOCKED")
        features_line = re.search(r"\*\*Features:\*\*\s*(.+)", content)
        feat_str = features_line.group(1).strip() if features_line else "?"
        report_link = f"[runs/completed/{completed.name}](runs/completed/{completed.name})"
        sprint_rows.append(
            f"| {sprint_d} | {feat_str} | {n_selected} | {n_pass} | {n_fail} | {n_blocked} | {report_link} |"
        )

    # Build fail/never lists
    fail_list: list[str] = []
    overdue_list: list[str] = []
    today = date.today()

    for tc_id, tc_hist in tcs.items():
        if tc_hist.get("last_result") == "FAIL":
            fail_list.append(f"- {tc_id} (last: {tc_hist.get('last_run', '?')})")
        last_run_str = tc_hist.get("last_run")
        if last_run_str and tc_hist.get("last_result") == "PASS":
            days = (today - datetime.strptime(last_run_str, "%Y-%m-%d").date()).days
            if days >= 30:
                fail_list.append(f"- {tc_id} ({days}d ago)")

    # All known features in display order
    all_features = [
        ("ver", "mc version", "VER"),
        ("upd", "mc-update", "UCHK/UUPG/UPIN/UUPN"),
        ("att", "mc attachments", "ATT"),
        ("chk", "mc check", "CHK"),
        ("new", "mc create", "NEW"),
        ("cmt", "mc comments", "CMT"),
        ("cs", "mc case", "CS"),
        ("who", "mc ldap", "WHO"),
        ("url", "mc launch", "URL"),
        ("agt", "mc agent", "AGT"),
    ]

    feature_rows = []
    for feature_key, feature_name, prefix_str in all_features:
        total = tc_counts.get(feature_key, 0)
        stats = feature_stats.get(feature_key, {})
        last_sprint = stats.get("last_sprint") or "—"
        n_pass = stats.get("pass", 0)
        n_fail = stats.get("fail", 0)
        n_blocked = stats.get("blocked", 0)
        n_never = total - n_pass - n_fail - n_blocked
        feature_rows.append(
            f"| {feature_name} | {prefix_str} | {total} | {last_sprint} "
            f"| {n_pass if n_pass else '—'} "
            f"| {n_fail if n_fail else '—'} "
            f"| {n_blocked if n_blocked else '—'} "
            f"| {n_never if n_never else '—'} |"
        )

    last_updated = sprint_date
    sprint_table = "\n".join(sprint_rows) if sprint_rows else "| *(none yet)* | | | | | | |"
    feature_table = "\n".join(feature_rows)
    fail_section = "\n".join(fail_list) if fail_list else "*(none)*"
    overdue_section = "\n".join(overdue_list) if overdue_list else "*(none)*"

    content = f"""# UAT Status Dashboard

> Updated by `scripts/uat/process_sprint.py` after each sprint is processed.
> Last updated: {last_updated}

---

## Feature Status

| Feature | Prefix | TCs | Last Sprint | Pass | Fail | Blocked | Never Run |
|---|---|---|---|---|---|---|---|
{feature_table}

---

## Sprint History

| Date | Features | Selected | Pass | Fail | Blocked | Report |
|---|---|---|---|---|---|---|
{sprint_table}

---

## TCs Awaiting Retest (last result: FAIL)

{fail_section}

---

## TCs Overdue for Regression (>30 days since last PASS)

{overdue_section}
"""
    STATUS_FILE.write_text(content)


def _prefix_to_feature(prefix: str, feature_map: dict[str, Any]) -> str | None:
    """Map a TC prefix (e.g. UPIN) to a feature key (e.g. upd)."""
    for _binary, features in feature_map.items():
        for feature_key, meta in features.items():
            if prefix in meta.get("prefixes", []):
                return feature_key
    return None


def main() -> None:
    sprint_date_arg = None
    dry_run = "--dry-run" in sys.argv

    if "--sprint" in sys.argv:
        idx = sys.argv.index("--sprint")
        if idx + 1 < len(sys.argv):
            sprint_date_arg = sys.argv[idx + 1]

    sprint_file = find_pending_sprint(sprint_date_arg)
    sprint_date, results = parse_sprint_file(sprint_file)

    # Check for unrecorded TCs
    unrecorded = [r for r in results if r["result"] is None]
    if unrecorded:
        ids = ", ".join(r["id"] for r in unrecorded)
        print(f"Warning: {len(unrecorded)} TCs have no result recorded: {ids}", file=sys.stderr)
        print("Proceeding — unrecorded TCs will not be saved to history.", file=sys.stderr)

    # Counts
    n_pass = sum(1 for r in results if r["result"] == "PASS")
    n_fail = sum(1 for r in results if r["result"] == "FAIL")
    n_blocked = sum(1 for r in results if r["result"] == "BLOCKED")
    n_total = len(results)

    print(f"\nSprint: {sprint_date}")
    print(f"Total: {n_total}  Pass: {n_pass}  Fail: {n_fail}  Blocked: {n_blocked}")
    print()

    # Jira output
    jira_output = build_jira_output(sprint_date, results)
    print(jira_output)

    if dry_run:
        print("[dry-run] No files updated.")
        return

    # Update history
    update_history(sprint_date, results)

    # Update STATUS.md
    update_status_md(sprint_date, results, HISTORY_FILE)

    # Move sprint file to completed
    COMPLETED_DIR.mkdir(parents=True, exist_ok=True)
    dest = COMPLETED_DIR / sprint_file.name
    shutil.move(str(sprint_file), str(dest))

    print(f"Sprint archived to: {dest.relative_to(ROOT)}")
    print(f"History updated: {HISTORY_FILE.relative_to(ROOT)}")
    print(f"Status updated: {STATUS_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
