---
name: uat-build-sprint-report
description: Generate a prose quality report for the most recently completed UAT sprint
argument-hint: "[YYYY-MM-DD]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
---

<objective>
Write a concise QA sprint report covering: what was tested, what passed/failed, risk assessment, and recommended follow-up actions. Outputs a markdown report alongside the completed sprint file.
</objective>

<context>
@tests/uat/STATUS.md
@tests/uat/data/tc_history.json
</context>

<process>

<step name="identify_sprint">
If a date argument was given, look for `tests/uat/runs/completed/YYYY-MM-DD.md`.
Otherwise, find the most recent completed sprint:
```bash
ls tests/uat/runs/completed/ | sort -r | head -5
```

If no completed sprints exist, tell the user to run `/uat-process-sprint` first.
</step>

<step name="load_sprint_data">
Read the completed sprint file in full.

Also read `tests/uat/data/tc_history.json` to get historical context:
- Has a failing TC failed before? (regression vs new failure)
- Has a passing TC been consistently passing? (stable)

Read `tests/uat/STATUS.md` for the overall feature status snapshot.
</step>

<step name="analyze_results">
For each TC in the sprint, classify:

**PASS:**
- First-time pass (was never run or previously failed) → "Fixed / now green"
- Consistent pass → "Stable"

**FAIL:**
- First-time failure → "New regression — needs investigation"
- Repeated failure → "Ongoing issue — already tracked"

**BLOCKED:**
- Note the blocking reason from Notes field
- Assess whether it is an environment issue (tester's machine) or a product issue

Compute:
- Pass rate for this sprint
- Pass rate trend vs previous sprint (if history available)
- Which features have never been tested (from STATUS.md)
</step>

<step name="write_report">
Write the report to `tests/uat/runs/completed/YYYY-MM-DD-report.md`:

```markdown
# UAT Sprint Report — YYYY-MM-DD

## Summary

| Metric | Value |
|---|---|
| Sprint date | YYYY-MM-DD |
| TCs run | N |
| Pass | P (X%) |
| Fail | F |
| Blocked | B |
| Prior sprint pass rate | Y% (or N/A) |

## What Was Tested

<Features and brief description of coverage>

## Results Detail

### Passed

- **TC-ID: Title** — Stable / First-time pass
  ...

### Failed

- **TC-ID: Title** — New regression / Ongoing issue
  Notes: <tester notes>
  Recommended action: File Jira / run `/bug-to-test TC-ID`

### Blocked

- **TC-ID: Title**
  Notes: <reason>
  Recommended action: Resolve environment issue / reschedule

## Risk Assessment

<Brief paragraph: what is the overall quality signal from this sprint?>
<Call out any critical paths that are still untested (per STATUS.md)>

## Recommended Follow-up

1. <Action 1 — e.g. "File Jira for TC-UUPG-01 failure">
2. <Action 2 — e.g. "Run `/uat-review att` — mc attachments has never been tested">
3. <Action 3 — e.g. "Include TC-UPIN-02 in next sprint — BLOCKED this sprint">
```

After writing, tell the user the report path and offer to display it inline.
</step>

</process>
