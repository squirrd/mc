# TDD Issue Skill — Design Pseudocode

> **SUPERSEDED** — This file is the original design document and pseudocode.
> The skill has been implemented at `.claude/commands/tdd-issue/skill.md`.
> This file is kept for historical reference only. Do not edit — edit the skill directly.

Design notes and pseudocode for the `tdd-issue` Claude skill.
Based on the TDD-Issue flowchart.

---

## Overview

Two cooperating flows:

- **ORCHESTRATOR** — one per issue; manages the integration test, investigates root cause,
  spawns unit test agents, waits for green, then merges.
- **UNIT TEST AGENT** — one per source file that needs a unit test; writes the red test,
  fixes the src, loops until green, then merges back.

Multiple issues can be worked on simultaneously because each issue lives in its own git worktree.
Within a single issue, all unit test agents also run in parallel, each in their own nested worktree.

---

## Naming Conventions

```
Branch / Worktree pattern:

  Issue branch   : fix/<shortFixName>
  Issue worktree : .tdd/worktrees/fix/<shortFixName>

  Unit test branch   : fix/<shortFixName>/<unitTestName>
  Unit test worktree : .tdd/worktrees/fix/<shortFixName>/<unitTestName>

Examples:
  fix/container-attach-leak
  fix/container-attach-leak/test-terminal-cleanup
  fix/container-attach-leak/test-state-gc

  .tdd/worktrees/fix/container-attach-leak/
  .tdd/worktrees/fix/container-attach-leak/test-terminal-cleanup/
  .tdd/worktrees/fix/container-attach-leak/test-state-gc/
```

Rules:
- `<shortFixName>` — lowercase, hyphen-separated, 2–5 words max, describes the bug
- `<unitTestName>` — lowercase, hyphen-separated, starts with `test-`, describes the test
- Branch slashes are literal git branch namespacing (git supports this natively)
- Worktree directories mirror the branch path exactly

---

## Tracking File: `.tdd/issues/ISSUE_TRACKING.md`

Created on first use of the skill. Updated at every status transition.
One file tracks all active and completed issues.

### Schema

```markdown
# Issue Tracking

Last updated: YYYY-MM-DD HH:MM

---

## Active Issues

### fix/<shortFixName>

| Field       | Value                                           |
|-------------|-------------------------------------------------|
| Status      | IN_PROGRESS                                     |
| Created     | YYYY-MM-DD                                      |
| Description | One sentence summary of the bug                 |
| Branch      | fix/<shortFixName>                              |
| Worktree    | .tdd/worktrees/fix/<shortFixName>               |
| Source      | <bug report / ticket / UAT ref / ad-hoc>        |
| Severity    | critical / major / minor                        |

#### Integration Tests

| Test Function                        | File                                | Status | Notes                     |
|--------------------------------------|-------------------------------------|--------|---------------------------|
| test_<bug>_regression                | tests/integration/test_<area>.py   | RED    | Added YYYY-MM-DD          |

#### Unit Tests

| Test Function         | Src File                   | Branch                                    | Worktree                                                  | Status |
|-----------------------|----------------------------|-------------------------------------------|-----------------------------------------------------------|--------|
| test_<name>           | src/mc/<module>.py         | fix/<shortFixName>/<unitTestName>         | .tdd/worktrees/fix/<shortFixName>/<unitTestName>          | RED    |
| test_<name2>          | src/mc/<module2>.py        | fix/<shortFixName>/<unitTestName2>        | .tdd/worktrees/fix/<shortFixName>/<unitTestName2>         | GREEN  |

---

## Completed Issues

### fix/<shortFixName>

| Field       | Value                                           |
|-------------|-------------------------------------------------|
| Status      | DONE                                            |
| Created     | YYYY-MM-DD                                      |
| Completed   | YYYY-MM-DD                                      |
| Description | One sentence summary                            |
| Merged into | main                                            |

#### Integration Tests

| Test Function         | File                              | Status |
|-----------------------|-----------------------------------|--------|
| test_<bug>_regression | tests/integration/test_<area>.py | GREEN  |

#### Unit Tests

| Test Function | Src File           | Status        |
|---------------|--------------------|---------------|
| test_<name>   | src/mc/<module>.py | GREEN (merged)|
```

### Status Values

```
Issue status:
  OPEN         - defined, not yet started
  IN_PROGRESS  - actively being worked
  BLOCKED      - waiting on something external
  DONE         - integration test green, branch merged

Integration test status:
  RED          - test written, confirms the bug
  GREEN        - test passes, bug is fixed

Unit test status:
  RED          - test written, confirms missing/broken behaviour
  GREEN        - src fixed, test passes
  MERGED       - branch merged back into issue branch
```

---

## FLOW 1: ORCHESTRATOR

```
INPUT: issue description (from user or ticket/UAT ref)

─────────────────────────────────────────────────────────
SETUP
─────────────────────────────────────────────────────────

STEP 0: Bootstrap tracking infrastructure (once per repo)
  IF .tdd/issues/ISSUE_TRACKING.md does not exist:
    mkdir -p .tdd/issues/
    create .tdd/issues/ISSUE_TRACKING.md with empty schema
  IF .tdd/worktrees/ does not exist:
    mkdir -p .tdd/worktrees/
  RECORD .tdd/ in .gitignore (worktrees should not be committed)

─────────────────────────────────────────────────────────
PHASE 1 — Define & Reproduce
─────────────────────────────────────────────────────────

STEP 1: Define the issue
  - Collect from user:
      description        (what is broken)
      expected behaviour (what should happen)
      actual behaviour   (what does happen)
      severity           (critical / major / minor)
      source             (ticket, UAT ref, ad-hoc)
  - Derive <shortFixName> from description (2–5 words, hyphenated)
  - Add issue to ISSUE_TRACKING.md with status = IN_PROGRESS

STEP 2: Reproduce the issue
  - Run bash commands to observe the failure live
  - Capture: error message, stack trace, unexpected output
  - IF cannot reproduce:
      ask user for more context → return to STEP 1
  - Confirm reproduction before proceeding

─────────────────────────────────────────────────────────
PHASE 2 — Integration Test (RED)
─────────────────────────────────────────────────────────

STEP 3: Create the issue worktree and branch
  git checkout -b fix/<shortFixName>              (from main)
  git worktree add .tdd/worktrees/fix/<shortFixName> fix/<shortFixName>
  ALL subsequent orchestrator work happens inside this worktree

STEP 4: Write integration test in RED condition
  - Create test in tests/integration/test_<area>.py
  - Test name: test_<shortFixDescription>_regression
  - Test docstring must include:
      bug description, steps to reproduce, expected vs actual,
      source reference (UAT / ticket / date)
  - Decorate: @pytest.mark.integration
  - Run the test → assert it FAILS (confirms it catches the bug)
  - IF test passes immediately:
      the bug may already be fixed → re-examine assumptions
  - Update ISSUE_TRACKING.md: integration test row, status = RED

─────────────────────────────────────────────────────────
PHASE 3 — Root Cause & Unit Test Agents
─────────────────────────────────────────────────────────

STEP 5: Investigate the cause of the issue
  - Read relevant source files
  - Trace execution path from the failing integration test
  - Understand the root cause

STEP 6: Identify source files that need fixing
  - Produce list: [src_file_1, src_file_2, ...]
  - For each src_file assess:

    DECISION: Does this src_file require a new/updated unit test for coverage?

    IF YES → assign a <unitTestName> (e.g. test-terminal-cleanup)
             record in ISSUE_TRACKING.md with status = RED
             → queue for UNIT TEST AGENT (FLOW 2)

    IF NO  → fix inline directly in the issue worktree (no sub-agent needed)

STEP 7: Spawn UNIT TEST AGENTs in parallel
  - For each src_file queued above, launch FLOW 2 concurrently
  - Each agent works in its own worktree (see naming conventions)
  - Orchestrator does NOT block — continue to STEP 8

STEP 8: Wait for all agents to report GREEN
  - Poll / receive signals from sub-agents
  - Update ISSUE_TRACKING.md unit test rows as each reports back
  - IF any agent reports BLOCKED or stuck:
      investigate that specific src_file and assist or reassign

─────────────────────────────────────────────────────────
PHASE 4 — Integration Test (GREEN) and Merge
─────────────────────────────────────────────────────────

STEP 9: Run the integration test
  - Execute from inside the issue worktree
  - All unit test branches should be merged into fix/<shortFixName> by now

  IF RED:
    → all unit tests green but integration still red
    → something deeper was missed
    → return to STEP 5 (investigate further)

  IF GREEN:
    → proceed to STEP 10

STEP 10: Merge the issue branch
  - git checkout main
  - git merge --no-ff fix/<shortFixName>
  - git commit (with summary of what was fixed)
  - git worktree remove .tdd/worktrees/fix/<shortFixName>
  - git branch -d fix/<shortFixName>

STEP 11: Update tracking
  - Update ISSUE_TRACKING.md:
      move issue from ## Active Issues to ## Completed Issues
      set status = DONE
      set completed date
      set integration test status = GREEN
      set all unit test statuses = GREEN (merged)

END
```

---

## FLOW 2: UNIT TEST AGENT (sub-agent, one per source file)

```
INPUT:
  issue_branch    : fix/<shortFixName>
  src_file        : path to source file being fixed
  issue_summary   : brief description of the bug
  <unitTestName>  : assigned by orchestrator

─────────────────────────────────────────────────────────

STEP A: Create the unit test worktree and branch
  git checkout -b fix/<shortFixName>/<unitTestName>    (from fix/<shortFixName>)
  git worktree add \
    .tdd/worktrees/fix/<shortFixName>/<unitTestName> \
    fix/<shortFixName>/<unitTestName>
  ALL work happens inside this worktree

STEP B: Write unit test in RED condition
  - Read src_file to understand current implementation
  - Locate or create test file: tests/unit/test_<module>.py
  - Write focused unit test targeting the broken behaviour
  - Test name must be descriptive: test_<specific_scenario>_<expected_outcome>
  - Run unit test → assert it FAILS (confirms red)
  - IF test passes immediately:
      re-examine test logic — it may not be targeting the right behaviour
  - Signal orchestrator: unit test row status = RED (if not already set)

STEP C: Fix the source file to create GREEN condition
  - Modify src_file only — minimal change to fix the root cause
  - No unrelated refactoring here
  - Run unit test

  IF RED:
    → fix is incomplete or incorrect
    → adjust implementation
    → re-run unit test
    → loop (bounded: max 5 attempts before flagging to orchestrator)

  IF GREEN:
    → proceed to STEP D

STEP D: Refactor (optional, lightweight)
  - Clean up implementation if needed
  - No behaviour changes
  - Re-run unit test — must still be GREEN
  - Run full unit test suite to check for regressions:
      uv run pytest tests/unit/ -v --no-cov -q

STEP E: Merge back and clean up
  - Commit in the unit test worktree:
      git add <src_file> <test_file>
      git commit -m "fix(<module>): <what was fixed>

      Unit test: test_<name>
      Part of: fix/<shortFixName>
      Root cause: <one sentence>"

  - Switch to issue branch and merge:
      git checkout fix/<shortFixName>
      git merge --no-ff fix/<shortFixName>/<unitTestName>

  - Remove worktree and branch:
      git worktree remove .tdd/worktrees/fix/<shortFixName>/<unitTestName>
      git branch -d fix/<shortFixName>/<unitTestName>

  - Update ISSUE_TRACKING.md: unit test row status = MERGED

  - Signal orchestrator: GREEN

OUTPUT: GREEN signal to FLOW 1 STEP 8
```

---

## Key Design Decisions

### Worktrees enable true parallelism
Each issue and each unit test sub-agent has its own working directory.
They share the git object store but operate on independent branches.
No file conflicts between concurrent agents.

### Branch hierarchy encodes relationships
`fix/<shortFixName>/<unitTestName>` is namespaced under the issue branch.
When you list branches (`git branch`) the grouping is visually clear.
Sub-agent branches always merge INTO their parent issue branch, never to main directly.

### ISSUE_TRACKING.md is the single source of truth
Updated at every status transition by both orchestrator and sub-agents.
Allows the user to check status of all in-flight issues at a glance.
Persists across context resets — the skill can resume by reading this file.

### Integration test is the acceptance criterion
Nothing merges to main until the integration test written in STEP 4 is GREEN.
If unit tests go green but integration stays red, root cause investigation restarts.
This prevents "fixed in isolation, broken end-to-end" scenarios.

### The RED loop in STEP 9 is bounded investigation, not retry
Returning to STEP 5 means genuinely re-reading and re-analysing.
The agent must not blindly retry the same fix approach.

---

## ISSUE_TRACKING.md — Lifecycle Example

```
Start:
  Issue added, status = IN_PROGRESS

After STEP 4:
  Integration test row added, status = RED

After STEP 6:
  Unit test rows added, status = RED

As sub-agents complete STEP E:
  Unit test rows update to GREEN → MERGED

After STEP 9 (integration GREEN):
  Issue moves to Completed, all statuses updated to DONE / GREEN
```

---

## Directory Layout (runtime)

```
.tdd/
├── issues/
│   └── ISSUE_TRACKING.md          <- single tracking file for all issues
└── worktrees/
    └── fix/
        ├── <shortFixName>/         <- issue orchestrator worktree
        │   ├── <unitTestName>/     <- unit test agent worktree
        │   └── <unitTestName2>/    <- unit test agent worktree (parallel)
        └── <anotherFix>/           <- second issue (concurrent)
            └── <unitTestName>/
```

`.tdd/` must be in `.gitignore` — worktrees are local only.

---

## Failure Modes and Guardrails

```
Unit test agent stuck in RED loop (STEP C):
  After 5 attempts, agent signals BLOCKED to orchestrator.
  Orchestrator pauses, flags to user, may reassign or assist.

Integration test stays RED after all units GREEN (STEP 9 → STEP 5):
  Indicates a multi-file interaction bug or missed src_file.
  Orchestrator re-investigates — reads interaction between the fixed files.
  May spawn additional unit test agents for newly discovered srcs.

Worktree conflict (branch already exists):
  Check git worktree list before creating.
  If stale worktree exists from a crashed prior session:
    git worktree prune
    git worktree remove --force .tdd/worktrees/fix/<name>
  Resume from ISSUE_TRACKING.md state.

Context reset mid-issue:
  Read ISSUE_TRACKING.md to restore state.
  Active issues still have their worktrees on disk — resume from last known status.
```

---

## TODO Before Turning Into Actual Skill File

- [ ] Decide: should ISSUE_TRACKING.md updates be done by the agent or via a helper bash script?
- [ ] Define max parallelism limits (MAX_PARALLEL_ISSUES, MAX_PARALLEL_UNIT_AGENTS)
- [ ] Decide: does the skill accept an argument (issue description) or always ask interactively?
- [ ] Define how sub-agents signal back to orchestrator (Task tool output parsing)
- [ ] Add `@pytest.mark.backwards_compatibility` considerations for unit tests touching public APIs
- [ ] Integrate with existing `bug-to-test` skill for the integration test creation step (STEP 4)
