---
name: uat-process-sprint
description: Process a completed sprint file — parse results, print failed TCs in Jira format, update history and STATUS.md, archive the sprint
argument-hint: "[YYYY-MM-DD] [--dry-run]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
---

<objective>
Process a completed UAT sprint. Use the process_sprint.py script to do all parsing and file updates. Present Jira-format failures clearly and confirm archiving.
</objective>

<context>
@tests/uat/STATUS.md
@tests/uat/runs/pending/
</context>

<process>

<step name="identify_sprint">
Check for pending sprint files:
```bash
ls tests/uat/runs/pending/
```

If a specific date was given as argument, target that file.
Otherwise use the most recent pending sprint.

If no pending sprints exist, tell the user there is nothing to process.
</step>

<step name="check_completeness">
Read the pending sprint file. Check that all TCs have a result recorded (`[x] PASS`, `[x] FAIL`, or `[x] BLOCKED`).

If any TCs have no result (`[ ] PASS`, `[ ] FAIL`, `[ ] BLOCKED` all unchecked):
- List the incomplete TCs
- Ask: "These TCs have no result. Process anyway (they will be skipped in history), or go back to complete them?"
</step>

<step name="run_process_script">
Run the processing script:

```bash
python3 scripts/uat/process_sprint.py [--sprint YYYY-MM-DD] [--dry-run]
```

This script:
1. Parses all TC results from checkboxes in the sprint file
2. Updates `tests/uat/data/tc_history.json` with run date, result, and notes per TC
3. Updates `tests/uat/STATUS.md` (feature table + sprint history + fail/overdue lists)
4. Prints the Jira-format failure summary to stdout
5. Moves the sprint file from `runs/pending/` to `runs/completed/`

Capture and display the full stdout output (includes Jira format and confirmation messages).
</step>

<step name="present_results">
After the script runs, present:

**Sprint summary:**
- Total: N  Pass: P  Fail: F  Blocked: B
- Pass rate: X%

**Jira failures** (from script output — display verbatim).

**Next steps:**
- For each FAIL: suggest `/bug-to-test TC-ID` to convert the failure into an automated integration test
- If any TCs were BLOCKED: note they are auto-included in the next sprint at high priority
- Remind: run `/uat-sprint` when ready for the next sprint
</step>

</process>
