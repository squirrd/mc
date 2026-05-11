#!/usr/bin/env python3
"""
Parse all UAT feature files and output TC metadata as JSON.

Usage:
    python scripts/uat/parse_features.py [--feature FEATURE]

Output (stdout): JSON array of TC objects with metadata + history merged in.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent.parent
FEATURES_DIR = ROOT / "tests/uat/features"
HISTORY_FILE = ROOT / "tests/uat/data/tc_history.json"

# Matches: ### TC-VER-01: Title
TC_HEADER_RE = re.compile(r"^### (TC-[A-Z]+-\d+): (.+)$", re.MULTILINE)

# Matches field lines like: **Pre-requires:** TC-UPIN-01 (reason)
FIELD_RE = {
    "pre_requires": re.compile(r"\*\*Pre-requires:\*\*\s*(.+)"),
    "cross_deps": re.compile(r"\*\*Cross-deps:\*\*\s*(.+)"),
    "tags": re.compile(r"\*\*Tags:\*\*\s*(.+)"),
}

SECTION_HEADERS = ["Goal", "Setup", "Steps", "Expected", "Result"]
SECTION_RE = re.compile(r"^\*\*(" + "|".join(SECTION_HEADERS) + r"):\*\*", re.MULTILINE)


def load_history() -> dict[str, Any]:
    if HISTORY_FILE.exists():
        data = json.loads(HISTORY_FILE.read_text())
        return data.get("tcs", {})
    return {}


def parse_tc_block(tc_id: str, title: str, block: str, feature: str) -> dict[str, Any]:
    """Parse a single TC block into a metadata dict."""
    tc: dict[str, Any] = {
        "id": tc_id,
        "title": title,
        "feature": feature,
        "prefix": tc_id.rsplit("-", 1)[0].lstrip("TC-"),
        "pre_requires": [],
        "cross_deps": [],
        "tags": [],
    }

    for field, pattern in FIELD_RE.items():
        m = pattern.search(block)
        if not m:
            continue
        value = m.group(1).strip()
        if value.lower() == "none":
            continue
        if field == "tags":
            tc["tags"] = [t.strip() for t in value.split(",")]
        else:
            # Extract TC IDs from text like "TC-UPIN-01 (reason), TC-UPIN-02 (other)"
            tc[field] = re.findall(r"TC-[A-Z]+-\d+", value)

    # Extract runnable content sections (Goal, Setup, Steps, Expected)
    section_matches = list(SECTION_RE.finditer(block))
    for i, sm in enumerate(section_matches):
        name = sm.group(1).lower()
        if name == "result":
            continue
        start = sm.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(block)
        content = block[start:end].strip()
        # Goal is inline on the same line as the header
        if name == "goal":
            content = content.lstrip(": ").split("\n")[0].strip() if content else ""
        tc[name] = content

    return tc


def parse_feature_file(path: Path) -> list[dict[str, Any]]:
    """Parse all TCs from a feature file."""
    feature = path.stem  # e.g. "upd", "ver"
    content = path.read_text()
    tcs = []

    matches = list(TC_HEADER_RE.finditer(content))
    for i, match in enumerate(matches):
        tc_id = match.group(1)
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        block = content[start:end]
        tcs.append(parse_tc_block(tc_id, title, block, feature))

    return tcs


def merge_history(tcs: list[dict[str, Any]], history: dict[str, Any]) -> list[dict[str, Any]]:
    """Merge run history into TC metadata."""
    for tc in tcs:
        h = history.get(tc["id"], {})
        tc["last_run"] = h.get("last_run")
        tc["last_result"] = h.get("last_result")
        tc["run_count"] = h.get("run_count", 0)
        tc["history"] = h.get("history", [])
    return tcs


def main() -> None:
    feature_filter = None
    if "--feature" in sys.argv:
        idx = sys.argv.index("--feature")
        if idx + 1 < len(sys.argv):
            feature_filter = sys.argv[idx + 1]

    history = load_history()
    all_tcs: list[dict[str, Any]] = []

    for path in sorted(FEATURES_DIR.glob("*.md")):
        if feature_filter and path.stem != feature_filter:
            continue
        try:
            tcs = parse_feature_file(path)
            all_tcs.extend(tcs)
        except Exception as e:
            print(f"Warning: failed to parse {path.name}: {e}", file=sys.stderr)

    all_tcs = merge_history(all_tcs, history)
    print(json.dumps(all_tcs, indent=2))


if __name__ == "__main__":
    main()
