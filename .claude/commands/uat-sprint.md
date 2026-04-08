---
name: uat-sprint
description: Build a UAT sprint plan — scores TCs by git changes, failures awaiting retest, and regression overdue, then generates a runs/pending/YYYY-MM-DD.md sprint file
argument-hint: "[feature1 feature2 ...] [--max N] [--date YYYY-MM-DD]"
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
  - AskUserQuestion
---

<objective>
Build a focused, high-value UAT sprint plan. Use scripts to do all scoring and selection work, then present the proposed plan for user confirmation before saving.
</objective>

<context>
@tests/uat/STATUS.md
@tests/uat/data/feature_map.json
</context>

<process>

<step name="parse_args">
Parse skill arguments:
- Feature keys (e.g. `upd ver att`) → passed as `--features f1,f2,f3` to build_sprint.py
- `--max N` → override default max of 9 TCs
- `--date YYYY-MM-DD` → override sprint date (default: today)

If no args: run for all features.
</step>

<step name="run_build_script">
Run the sprint builder script. It handles all scoring and selection:

```bash
python3 scripts/uat/build_sprint.py \
  [--features <comma-separated>] \
  [--max <N>] \
  [--date <YYYY-MM-DD>]
```

The script:
- Loads all TC metadata from feature files + run history
- Gets git commits since last sprint (or last 30 days) via analyze_git.py
- Scores TCs:
  - Last result FAIL → 150 (must retest)
  - Never run → 100
  - Not run in >30 days → 50 (regression)
  - Not run in >14 days → 25
  - Source changed since last sprint → +75
- Auto-includes prerequisites (Pre-requires + Cross-deps)
- Writes the sprint plan to `runs/pending/YYYY-MM-DD.md`
- Outputs a JSON summary to stderr

Capture both stdout (file path confirmation) and stderr (JSON summary).
Parse the JSON summary from stderr for the next step.
</step>

<step name="present_plan">
Present the proposed sprint to the user in a readable summary:

```
Sprint: YYYY-MM-DD
Git analysis since: YYYY-MM-DD
Features covered: ver, upd

Selected TCs (N total):
  TC-VER-01  Basic version display           [never run]        score: 100
  TC-UUPG-01 Full upgrade end-to-end        [last failed]      score: 150
  TC-UPIN-01 Pin to specific version        [auto-prereq for UPIN-02]
  ...

Sprint file: tests/uat/runs/pending/YYYY-MM-DD.md
```

Highlight:
- Any TCs selected because of recent git changes (show the commit subject)
- Any TCs selected because they previously failed
- Any TCs auto-included as prerequisites
- Any features with NO TCs yet (suggest `/uat-review <feature>` to generate them)
</step>

<step name="confirm">
Ask the user:
"Sprint plan ready with N test cases. The file has been written to runs/pending/YYYY-MM-DD.md.

Open it to begin testing. When done, run `/uat-process-sprint` to record results.

Want to adjust anything? (e.g. add/remove features, change the max, add specific TCs)"

If the user wants adjustments:
- If removing TCs: edit the sprint file directly to remove those TC sections
- If adding TCs: append them from the relevant feature file
- If changing scope: re-run the build script with updated args
</step>

</process>
