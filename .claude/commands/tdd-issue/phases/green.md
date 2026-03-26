# Phase: Green — Surgeon (STEP 6, 7, 8, 9, 10)

This file is executed by a sub-agent spawned by the tdd-issue orchestrator.
Read it fully before taking any action.

---

## First action — Load reference doc

```
Read /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/references/agent-tdd-workflow.md
```

---

## Variables passed by orchestrator

| Variable | Description |
|---|---|
| `repo_root` | `/Users/dsquirre/Repos/mc` |
| `shortFixName` | e.g. `container-attach-leak` |
| `bugClass` | `host-only`, `host→container boundary`, or `in-container` |
| `reproSummary` | One sentence description of the bug |
| `integrationTestFile` | e.g. `tests/integration/test_container.py` |
| `integrationTestFunction` | e.g. `test_container_attach_leak_regression` |
| `resume_context` | Contents of resume.md if resuming, otherwise empty string |

Derived constants:
- `worktree_path` = `/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>`
- `issue_branch` = `fix/<shortFixName>`
- `issue_dir` = `/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>`

---

## On resume

If `resume_context` is non-empty AND it contains `completed_phases: [setup, red, green]`, skip ALL
steps and return immediately:

```json
{
  "phase": "green",
  "status": "DONE",
  "shortFixName": "<shortFixName>",
  "integrationTestFile": "<integrationTestFile>",
  "unitTestsFixed": 0,
  "details": "Resumed from saved state — green phase already complete"
}
```

---

## Test output pattern

All pytest runs in this phase use this pattern. Replace `<step>` with the step name:

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/test-<step>-${TIMESTAMP}.log"
cd <worktree_path> && PYTHONPATH=<worktree_path>/src \
  uv run pytest <test-target> -q --tb=short -p no:cov --override-ini="addopts=" 2>&1 | tee "$LOG_FILE"
echo ""
echo "--- Test summary (full output: $LOG_FILE) ---"
grep -E "^(FAILED|ERROR|E |AssertionError|====)" "$LOG_FILE" | head -25
```

> **If you need to diagnose a failure in detail:** `Read "$LOG_FILE"` — do not re-run with -v -s.

---

## STEP 6 — Investigate root cause via Explore subagent

Do NOT read source files directly in this phase's context. Instead, spawn an Explore subagent
to trace the execution path and return only a structured summary.

First, get the latest test failure output to provide as context. Read the most recent step5 log:
```bash
ls -t /Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/test-step5-*.log 2>/dev/null | head -1
```
Then `Read` that log file (last 50 lines is sufficient).

Spawn the Explore subagent:

```
Agent(
  subagent_type="Explore",
  description="Investigate root cause of fix/<shortFixName>",
  prompt="""
Investigate the root cause of this bug in the following codebase:

Working directory: /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>
Source root: /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src

Bug description: <reproSummary>
Bug class: <bugClass>
Failing test: <integrationTestFile>::<integrationTestFunction>

Test failure output:
<paste extracted failure lines from step5 log — FAILED/E /AssertionError lines>

Your task:
1. Read the failing test to understand what it exercises
2. Trace the execution path from the test entry point through the source code
3. Identify the exact root cause (file and line number)
4. Do NOT suggest fixes — only identify what is wrong and where

Return ONLY this structured format (no other text, no preamble):

ROOT_CAUSE: <one sentence, src/mc/module.py:line — what is wrong>
AFFECTED_FILES:
  - src/mc/module.py:line — <what is wrong here specifically>
FIX_HYPOTHESIS:
  - src/mc/module.py — <minimum change needed to fix this>
"""
)
```

Wait for the Explore subagent to return. Record its structured output as `investigation_result`.

Document findings before moving on:
```
Root cause: <ROOT_CAUSE from subagent>

Affected source files:
  - src/mc/<module1>.py:<line> — <what is wrong here>
  - src/mc/<module2>.py:<line> — <what is wrong here>
```

---

## STEP 7 — Triage source files

For each affected source file from the investigation, decide:

**DECISION: Does this src_file need a new or updated unit test?**

YES (needs a unit test) →
  - Assign a `<unitTestName>`: lowercase, hyphenated, starts with `test-`
    Example: `test-attach-fd-cleanup`
  - Check: does this change touch a public API method?
    - YES → set `backwards_compat = true` for the agent
  - Queue for UNIT TEST AGENT (STEP 8)
  - Add to tracking:
    ```bash
    bash /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/scripts/update-tracking.sh \
      --action add-unit-test \
      --issue "fix/<shortFixName>" \
      --unit-test "<unitTestName>" \
      --src-file "src/mc/<module>.py" \
      --branch "fix/<shortFixName>--<unitTestName>" \
      --status RED
    ```

NO (fix inline, no new unit test) →
  - Edit the file directly in the issue worktree
  - Coverage is already adequate for this path
  - Complete inline fixes before spawning agents

---

## STEP 8 — Spawn unit test agents in parallel

For each queued src_file, spawn one agent using the unit-test-agent template.
Maximum 5 concurrent agents. Spawn ALL before waiting for any.

> **Worktree + branching note:** Each unit test agent creates a nested branch
> `fix/<shortFixName>--<unitTestName>` from the issue branch `fix/<shortFixName>` (not from main).
> The worktree is created at `.tdd/worktrees/fix/<shortFixName>/<unitTestName>`.
> All merges go back into `fix/<shortFixName>`. This is handled by the agent via
> `create-worktree.sh` and `cleanup-worktree.sh --merge-into fix/<shortFixName>`.
> Do NOT modify this branching strategy.

Spawn template (run_in_background=True for all agents):

```
Agent(
  subagent_type="general-purpose",
  description="Unit test agent: fix/<shortFixName>--<unitTestName>",
  run_in_background=True,
  prompt="""
Read and follow ALL instructions at:
  /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/agents/unit-test-agent.md

Variables for this run:
  issue_branch:    fix/<shortFixName>
  src_file:        <src_file>
  issue_summary:   <reproSummary>
  unit_test_name:  <unitTestName>
  backwards_compat: <true|false>
  repo_root:       /Users/dsquirre/Repos/mc
"""
)
```

After spawning all agents, proceed immediately to STEP 9.

---

## STEP 9 — Wait for agent results and track

Use TaskOutput to collect results from each agent as they complete.
Parse the JSON output from each agent.

For each GREEN result:
```bash
bash /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action update-unit-test \
  --issue "fix/<shortFixName>" \
  --unit-test "<unitTestName>" \
  --status MERGED
```

For each BLOCKED result:
- Read the agent's `details` field to understand the blocker
- Investigate the source file and the test directly (in the issue worktree)
- Resolve the issue (edit source or test), then either:
  - Re-spawn the agent for that unit test, or
  - Fix it directly in the issue worktree

Display live status as agents report:
```
Unit test agents (fix/<shortFixName>):
  - test-attach-fd-cleanup:   GREEN (merged)
  - test-state-gc-cleanup:    in progress...
  - test-config-reload:       BLOCKED — see details
```

---

## STEP 10 — Run the integration test

All unit test branches should now be merged into `fix/<shortFixName>`.

> **Post-fix assertion review:** Before running the integration test, re-read its assertions
> in light of the fix. If the fix inverted a flag or changed API semantics, the assertions
> written during STEP 5 (RED) may now test the wrong condition. Verify that:
> - The assertion reflects the *correct post-fix behaviour*, not the pre-fix broken state
> - The test would still fail if you reintroduce the bug
> If the assertion is wrong, fix it now — this is correcting a mis-stated expectation,
> not a new RED/GREEN cycle.

Run using the test output pattern with `<step>=step10`:

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/test-step10-${TIMESTAMP}.log"
cd /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName> && \
  PYTHONPATH=/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src \
  uv run pytest <integrationTestFile>::<integrationTestFunction> \
    -q --tb=short -p no:cov --override-ini="addopts=" 2>&1 | tee "$LOG_FILE"
echo ""
echo "--- Test summary (full output: $LOG_FILE) ---"
grep -E "^(FAILED|ERROR|E |AssertionError|====)" "$LOG_FILE" | head -25
```

IF RED:
- Unit tests are green but integration still fails
- Something deeper was missed — multi-file interaction or uncovered code path
- Return to STEP 6 (re-investigate — spawn a fresh Explore subagent with the new failure context)
- Do NOT merge until GREEN
- Genuinely re-read and re-analyse — do NOT retry the same fix

IF GREEN:
```
Integration test GREEN: <integrationTestFunction> PASSED
Proceeding to merge.
```

Update tracking:
```bash
bash /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action update-integration-test \
  --issue "fix/<shortFixName>" \
  --test-function "<integrationTestFunction>" \
  --status GREEN
```

---

## End of phase — Update resume state

Update `/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/resume.md`:

```markdown
---
completed_phases: [setup, red, green]
current_phase: close
---

## State

short_fix_name: <shortFixName>
bug_class: <bugClass>
repro_summary: <reproSummary>
integration_test_file: <integrationTestFile>
integration_test_function: <integrationTestFunction>
unit_tests_fixed: <N>
```

---

## Output

```json
{
  "phase": "green",
  "status": "DONE",
  "shortFixName": "<shortFixName>",
  "integrationTestFile": "<integrationTestFile>",
  "integrationTestFunction": "<integrationTestFunction>",
  "unitTestsFixed": <N>,
  "details": "Integration test GREEN. <N> unit tests fixed and merged into fix/<shortFixName>."
}
```

**Anti-patterns:**
- Do NOT read many source files in this phase's context — use the Explore subagent
- Do NOT skip the Explore subagent even if you think you know the root cause
- Do NOT retry the same fix approach in the STEP 10 RED loop — genuinely re-investigate
- Do NOT spawn more than 5 unit test agents concurrently
- Do NOT modify the branching strategy — unit tests branch from issue branch, not from main
