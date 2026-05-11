#!/usr/bin/env python3
"""
Build a UAT sprint plan by scoring and selecting test cases.

Usage:
    python scripts/uat/build_sprint.py [--features f1,f2,...] [--max N] [--minutes M] [--date YYYY-MM-DD]

Scoring tiers (highest priority first):
    1. Never run              : 200
    2. Last FAIL or BLOCKED   : 150  (must retest)
    3. Recent git changes     : 75   (source touched since last sprint)
    4. Overdue regression >30d: 50   (oldest-first within this tier)

Sprint sizing:
    --max N       : Hard cap on TC count (default: 15)
    --minutes M   : Cap sprint by estimated duration
    TC time estimates from tags: fast=2min, network=5min, agent-mode=7min, default=3min

Output (stdout): Sprint plan markdown written to runs/pending/YYYY-MM-DD.md
                 Summary JSON written to stderr for skill consumption.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
FEATURES_DIR = ROOT / "tests/uat/features"
PENDING_DIR = ROOT / "tests/uat/runs/pending"
COMPLETED_DIR = ROOT / "tests/uat/runs/completed"
HISTORY_FILE = ROOT / "tests/uat/data/tc_history.json"
SCRIPTS_DIR = ROOT / "scripts/uat"

SCORE_NEVER_RUN = 200
SCORE_LAST_FAILED = 150
SCORE_GIT_CHANGE = 75
SCORE_OVERDUE_30 = 50
MAX_DEFAULT = 15

TAG_TIME_MINUTES: dict[str, int] = {
    "fast": 2,
    "network": 5,
    "mode: agent": 7,
}
DEFAULT_TIME_MINUTES = 3


def run_script(script: str, args: list[str]) -> Any:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script)] + args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"Warning: {script} failed: {result.stderr.strip()}", file=sys.stderr)
        return None
    if not result.stdout.strip():
        return None
    return json.loads(result.stdout)


def get_last_sprint_date() -> str | None:
    """Return the date of the most recently completed sprint, or None."""
    completed = sorted(COMPLETED_DIR.glob("*.md"), reverse=True)
    if completed:
        return completed[0].stem  # filename is YYYY-MM-DD
    # Fall back to pending (in case nothing completed yet)
    pending = sorted(PENDING_DIR.glob("*.md"), reverse=True)
    if pending:
        return pending[0].stem
    return None


def estimate_tc_minutes(tc: dict[str, Any]) -> int:
    """Estimate execution time in minutes from TC tags."""
    tags = tc.get("tags", [])
    max_time = DEFAULT_TIME_MINUTES
    for tag, minutes in TAG_TIME_MINUTES.items():
        if tag in tags:
            max_time = max(max_time, minutes)
    return max_time


def score_tcs(
    tcs: list[dict[str, Any]],
    git_changes: dict[str, list[dict[str, Any]]],
    today: date,
) -> list[dict[str, Any]]:
    """Score each TC and attach reason strings.

    Priority tiers:
      1. Never run (200)
      2. Last FAIL or BLOCKED (150)
      3. Recent git changes (+75, additive)
      4. Overdue regression >30 days (50, oldest-first tiebreaker)
    """
    scored = []
    for tc in tcs:
        score = 0
        reasons: list[str] = []
        days_since_run = 0

        last_result = tc.get("last_result")
        last_run_str = tc.get("last_run")
        last_run = datetime.strptime(last_run_str, "%Y-%m-%d").date() if last_run_str else None

        if last_run is None:
            score += SCORE_NEVER_RUN
            reasons.append("Never run")
            days_since_run = 9999
        elif last_result in ("FAIL", "BLOCKED"):
            score += SCORE_LAST_FAILED
            reasons.append(f"Last run {last_result} ({last_run_str})")
            days_since_run = (today - last_run).days
        else:
            days_since_run = (today - last_run).days
            if days_since_run >= 30:
                score += SCORE_OVERDUE_30
                reasons.append(f"Overdue regression ({days_since_run}d since last PASS)")

        feature_commits = git_changes.get(tc["feature"], [])
        if feature_commits:
            score += SCORE_GIT_CHANGE
            subjects = [c["subject"][:60] for c in feature_commits[:3]]
            reasons.append(f"Source changed: {'; '.join(subjects)}")

        tc["score"] = score
        tc["reasons"] = reasons
        tc["days_since_run"] = days_since_run
        tc["est_minutes"] = estimate_tc_minutes(tc)
        scored.append(tc)

    return sorted(scored, key=lambda t: (-t["score"], -t["days_since_run"]))


def resolve_prerequisites(
    selected_ids: list[str], all_tcs: dict[str, dict[str, Any]]
) -> list[str]:
    """Expand selected list to include all pre-requires and cross-deps (recursive)."""
    resolved: list[str] = []
    seen: set[str] = set()
    queue = list(selected_ids)

    while queue:
        tc_id = queue.pop(0)
        if tc_id in seen:
            continue
        seen.add(tc_id)
        resolved.append(tc_id)

        tc = all_tcs.get(tc_id)
        if not tc:
            continue
        for dep in tc.get("pre_requires", []) + tc.get("cross_deps", []):
            if dep not in seen:
                queue.append(dep)

    # Preserve dependency order: prerequisites come before their dependents
    ordered: list[str] = []
    added: set[str] = set()

    def add_with_deps(tc_id: str) -> None:
        if tc_id in added:
            return
        tc = all_tcs.get(tc_id)
        if tc:
            for dep in tc.get("pre_requires", []) + tc.get("cross_deps", []):
                add_with_deps(dep)
        added.add(tc_id)
        ordered.append(tc_id)

    for tc_id in resolved:
        add_with_deps(tc_id)

    return ordered


def generate_sprint_markdown(
    sprint_date: str,
    features: list[str],
    ordered_tc_ids: list[str],
    all_tcs: dict[str, dict[str, Any]],
    git_changes: dict[str, list[dict[str, Any]]],
    rationale_map: dict[str, list[str]],
) -> str:
    est_total = sum(all_tcs[tc_id].get("est_minutes", DEFAULT_TIME_MINUTES) for tc_id in ordered_tc_ids if tc_id in all_tcs)

    lines = [
        f"# UAT Sprint: {sprint_date}",
        "",
        f"**Generated:** {sprint_date}",
        f"**Features:** {', '.join(sorted(features))}",
        f"**Total TCs:** {len(ordered_tc_ids)}",
        f"**Estimated time:** ~{est_total} minutes",
        "",
        "**How to run:**",
        "1. Work through each TC below — steps are included inline",
        "2. Mark exactly one checkbox per TC",
        "3. Add notes for any FAIL or BLOCKED result",
        "4. When done: run `/uat-process-sprint`",
        "",
        "---",
        "",
    ]

    current_feature = None
    for tc_id in ordered_tc_ids:
        tc = all_tcs.get(tc_id)
        if not tc:
            continue

        if tc["feature"] != current_feature:
            current_feature = tc["feature"]
            lines.append(f"## Feature: {current_feature}")
            lines.append("")

        prereqs = tc.get("pre_requires", [])
        cross_deps = tc.get("cross_deps", [])
        reasons = rationale_map.get(tc_id, ["Auto-included as prerequisite"])
        tags = tc.get("tags", [])
        last_run = tc.get("last_run") or "never"
        last_result = tc.get("last_result") or "never run"

        lines += [
            f"### {tc_id}: {tc['title']}",
            "",
            f"**Feature file:** `tests/uat/features/{tc['feature']}.md`",
            f"**Tags:** {', '.join(tags) if tags else '—'}",
            f"**Last run:** {last_run} ({last_result})",
        ]

        if prereqs:
            lines.append(f"**Pre-requires:** {', '.join(prereqs)}")
        if cross_deps:
            lines.append(f"**Cross-deps:** {', '.join(cross_deps)}")

        lines += [
            f"**Selected because:** {'; '.join(reasons)}",
            "",
        ]

        goal = tc.get("goal")
        setup = tc.get("setup")
        steps = tc.get("steps")
        expected = tc.get("expected")

        if goal:
            lines += [f"**Goal:** {goal}", ""]
        if setup:
            lines += ["**Setup:**", setup, ""]
        if steps:
            lines += ["**Steps:**", steps, ""]
        if expected:
            lines += ["**Expected:**", expected, ""]

        lines += [
            "**Result:**",
            "- [ ] PASS",
            "- [ ] FAIL",
            "- [ ] BLOCKED",
            "",
            "**Notes:** <!-- required if FAIL or BLOCKED -->",
            "",
            "---",
            "",
        ]

    return "\n".join(lines)


def main() -> None:
    today = date.today()
    sprint_date = today.isoformat()
    max_tcs = MAX_DEFAULT
    max_minutes: int | None = None
    feature_filter: list[str] | None = None

    if "--date" in sys.argv:
        idx = sys.argv.index("--date")
        if idx + 1 < len(sys.argv):
            sprint_date = sys.argv[idx + 1]

    if "--max" in sys.argv:
        idx = sys.argv.index("--max")
        if idx + 1 < len(sys.argv):
            max_tcs = int(sys.argv[idx + 1])

    if "--minutes" in sys.argv:
        idx = sys.argv.index("--minutes")
        if idx + 1 < len(sys.argv):
            max_minutes = int(sys.argv[idx + 1])

    if "--features" in sys.argv:
        idx = sys.argv.index("--features")
        if idx + 1 < len(sys.argv):
            feature_filter = sys.argv[idx + 1].split(",")

    # Check for existing sprint on this date
    pending_file = PENDING_DIR / f"{sprint_date}.md"
    if pending_file.exists():
        print(
            f"Error: Sprint {sprint_date} already exists at {pending_file}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Load all TCs from feature files
    parse_args = []
    all_tc_list: list[dict[str, Any]] = run_script("parse_features.py", parse_args) or []

    if not all_tc_list:
        print("Error: No TCs found in feature files.", file=sys.stderr)
        sys.exit(1)

    # Filter by feature if requested
    if feature_filter:
        all_tc_list = [tc for tc in all_tc_list if tc["feature"] in feature_filter]

    all_tcs = {tc["id"]: tc for tc in all_tc_list}

    # Get git changes since last sprint (or 30 days ago as fallback)
    last_sprint = get_last_sprint_date()
    since_date = last_sprint or (today - timedelta(days=30)).isoformat()

    git_changes: dict[str, list[dict[str, Any]]] = (
        run_script("analyze_git.py", ["--since", since_date]) or {}
    )

    # Score TCs
    scored_tcs = score_tcs(all_tc_list, git_changes, today)

    # Select TCs by score, respecting --max and --minutes caps
    eligible = [tc for tc in scored_tcs if tc["score"] > 0]
    if not eligible:
        eligible = scored_tcs

    selected: list[dict[str, Any]] = []
    total_minutes = 0
    for tc in eligible:
        if len(selected) >= max_tcs:
            break
        est = tc.get("est_minutes", DEFAULT_TIME_MINUTES)
        if max_minutes is not None and total_minutes + est > max_minutes:
            continue
        selected.append(tc)
        total_minutes += est

    selected_ids = [tc["id"] for tc in selected]

    # Build rationale map before resolving prerequisites
    rationale_map: dict[str, list[str]] = {
        tc["id"]: tc["reasons"] for tc in eligible if tc["id"] in selected_ids
    }

    # Expand to include prerequisites
    ordered_ids = resolve_prerequisites(selected_ids, all_tcs)

    # Collect features represented
    features_represented = sorted({all_tcs[tc_id]["feature"] for tc_id in ordered_ids if tc_id in all_tcs})

    # Generate markdown
    markdown = generate_sprint_markdown(
        sprint_date,
        features_represented,
        ordered_ids,
        all_tcs,
        git_changes,
        rationale_map,
    )

    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    pending_file.write_text(markdown)

    # Compute total estimated time
    est_total = sum(all_tcs[tc_id].get("est_minutes", DEFAULT_TIME_MINUTES) for tc_id in ordered_ids if tc_id in all_tcs)

    # Summary to stderr for skill consumption
    summary = {
        "sprint_date": sprint_date,
        "output_file": str(pending_file.relative_to(ROOT)),
        "tc_count": len(ordered_ids),
        "est_minutes": est_total,
        "max_minutes": max_minutes,
        "features": features_represented,
        "since_date": since_date,
        "tcs": [
            {
                "id": tc_id,
                "title": all_tcs[tc_id]["title"] if tc_id in all_tcs else "?",
                "score": all_tcs[tc_id].get("score", 0) if tc_id in all_tcs else 0,
                "est_minutes": all_tcs[tc_id].get("est_minutes", DEFAULT_TIME_MINUTES) if tc_id in all_tcs else DEFAULT_TIME_MINUTES,
                "reasons": rationale_map.get(tc_id, ["auto-prerequisite"]),
            }
            for tc_id in ordered_ids
        ],
    }
    print(json.dumps(summary, indent=2), file=sys.stderr)
    print(f"Sprint written to: {pending_file.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
