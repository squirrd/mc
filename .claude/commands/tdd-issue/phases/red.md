# Phase: Red — Prosecutor (STEP 3, 4, 4.3, 4.5, 5)

This file is executed by a sub-agent spawned by the tdd-issue orchestrator.
Read it fully before taking any action.

---

## First action — Load reference doc

```
Read /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/references/tdd-principles.md
```

---

## Variables passed by orchestrator

| Variable | Description |
|---|---|
| `repo_root` | `/Users/dsquirre/Repos/mc` |
| `shortFixName` | e.g. `container-attach-leak` |
| `bugClass` | `host-only`, `host→container boundary`, or `in-container` |
| `reproSummary` | One sentence description of the bug |
| `errorMessage` | Exact error from reproduction |
| `severity` | `critical`, `major`, or `minor` |
| `source` | UAT ref / ticket / ad-hoc |
| `resume_context` | Contents of resume.md if resuming, otherwise empty string |

Derived constants used throughout this phase:
- `worktree_path` = `/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>`
- `issue_branch` = `fix/<shortFixName>`
- `issue_dir` = `/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>`

---

## On resume

If `resume_context` is non-empty AND it contains `completed_phases: [setup, red]`, skip ALL steps
and recover state from tracking file:

```bash
grep -A 5 "### fix/<shortFixName>" /Users/dsquirre/Repos/mc/.tdd/issues/ISSUE_TRACKING.md
```

Return immediately with recovered `integrationTestFile` and `integrationTestFunction`:

```json
{
  "phase": "red",
  "status": "DONE",
  "shortFixName": "<shortFixName>",
  "integrationTestFile": "<from tracking>",
  "integrationTestFunction": "<from tracking>",
  "details": "Resumed from saved state — red phase already complete"
}
```

---

## Test output pattern

All pytest runs in this phase use this pattern. Replace `<step>` with the step name (e.g. `step4`, `step5`):

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

## STEP 3 — Create issue worktree + branch

```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/create-worktree.sh fix/<shortFixName>
```

This creates:
- Branch: `fix/<shortFixName>` (from main)
- Worktree: `.tdd/worktrees/fix/<shortFixName>`

Add the issue to the tracking file:

```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action add-issue \
  --issue "fix/<shortFixName>" \
  --description "<one sentence bug description>" \
  --severity "<critical|major|minor>" \
  --source "<UAT ref / ticket / ad-hoc>"
```

---

## STEP 4 — Write temp repro test (prove the bug exists)

Do NOT touch source code yet.

Create `tests/temp_repro.py` inside the issue worktree:
```
/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/tests/temp_repro.py
```

Requirements:
- Minimal pytest test that triggers the exact bug
- Uses real components (do not mock the thing being tested)
- Has a clear assertion that FAILS when the bug is present
- Has a comment explaining why it should fail

**Verification depth — match the test to the bug class:**

- **host-only** — assert on host-side state: return values, files on disk, CLI stdout/exit code.
  No container needed.

- **host→container boundary** — the test MUST verify the end state inside a real container.
  Asserting on the Python object that was supposed to produce the artifact is not enough.
  Use `podman exec` or `subprocess` to check the actual in-container result:
  ```python
  result = subprocess.run(
      ["podman", "exec", container_name, "bash", "-c",
       f"source {bashrc_path} && echo $HTTPS_PROXY"],
      capture_output=True, text=True, check=True,
  )
  assert proxy_value in result.stdout
  ```

- **in-container** — exec the failing command in a real running container and assert on
  its stdout/stderr/exit code.

> **Trap to avoid:** For host→container and in-container bugs, do NOT write a test that only
> checks an intermediate Python value. If the test can pass without a container running, it is
> almost certainly testing at the wrong depth.

> **Worktree pytest note:** Each Bash call resets CWD — always use `cd /absolute/path && command`
> in a single call. Use `-p no:cov` (not `--no-cov`). Add `--override-ini="addopts="` to prevent
> `pyproject.toml`'s `addopts` from injecting coverage flags. Set `PYTHONPATH` to the worktree's
> `src/` so Python resolves `mc` from the worktree source tree, not the main repo's editable install.

Run it and assert FAIL (RED) using the test output pattern above with `<step>=step4`:

IF test PASSES immediately:
- The test does not reproduce the bug — revise it
- Do NOT proceed until the test FAILS

Display RED confirmation:
```
RED confirmed: tests/temp_repro.py FAILS as expected.
Error: <exact failure message from log>
```

---

## STEP 4.3 — Existing integration test audit (false positive scan)

Before writing any permanent test, scan existing integration tests in the affected area
to find any that are currently **passing but should be failing** given the confirmed bug.

**Identify the target test file(s)** from the bug's affected module:
- `terminal/`     → `tests/integration/test_terminal.py`
- `container/`   → `tests/integration/test_container.py`
- `config/`      → `tests/integration/test_config.py`
- `integrations/` → `tests/integration/test_<service>.py`

**Grep for existing tests** in the target file:
```bash
grep -n "def test_" /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/tests/integration/test_<area>.py
```

Read candidate test functions. For each that *appears* to cover the affected behaviour, ask:
> "If this bug is present, should this test fail?"

- If YES and it currently PASSES → it is a false positive — run it to confirm:
  ```bash
  cd /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName> && \
  PYTHONPATH=/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src \
  uv run pytest tests/integration/test_<area>.py::test_<candidate> \
    -q --tb=short -p no:cov --override-ini="addopts=" 2>&1 | head -30
  ```
  Identify the weak assertion that allows it to pass despite the bug.

Document findings:
```
False positive audit:
  - test_<name>: PASSES but should FAIL — assertion checks <X> not <Y>
  - test_<name>: correctly skips this code path (not a false positive)
  (none found — existing tests do not cover this code path)
```

---

## STEP 4.5 — Sanity check (human gate)

Present a structured brief and wait for explicit approval via AskUserQuestion.

Format:

```
BUG BRIEF — fix/<shortFixName>
═══════════════════════════════════════════════════════════
Bug class    : <host-only | host→container boundary | in-container>
Reproduced   : YES — <exact error from RED test, one line>
Root cause   : <one sentence, file:line if known>
Confidence   : <HIGH | MEDIUM | LOW>  (<reason if not HIGH>)
Unknowns     : <none | list any open questions>

False positives found
───────────────────────────────────────────────────────────
  <test_name> in tests/integration/<file>.py
    Passes now because: <weak assertion>
    Will be fixed: tighten assertion to verify <correct observable behaviour>
  (none — no existing tests cover this code path)

Fix plan
───────────────────────────────────────────────────────────
  Source files to change:
    - <src_file>:<line> — <what changes>
  Tests to add/update:
    - <integration test name>  [new — permanent RED]
    - <false positive test name> — tighten assertion
    - <unit test name(s)> if applicable

On approval, next actions:
  1. Write failing integration test (permanent RED)
  2. Fix false positive test assertions
  3. Fix <src_file>
  4. Verify all tests GREEN
  5. Clean up worktree (branch stays on fix/<shortFixName> for review)
═══════════════════════════════════════════════════════════
[Plan Approved] — proceed with the fix plan above
[Discuss] — ask a question or raise a concern
```

**Response handling:**

- `Plan Approved` → delete `tests/temp_repro.py`, proceed to STEP 5
- `Discuss` → address the user's question or concern, update the brief if needed, re-present
  for approval (loop until `Plan Approved`)
  - If the user indicates they want to cancel during discussion, delete `tests/temp_repro.py`,
    clean up worktree, and close the issue as CANCELLED:
    ```bash
    cd /Users/dsquirre/Repos/mc
    bash .claude/commands/tdd-issue/scripts/cleanup-worktree.sh "fix/<shortFixName>"
    bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
      --action close-issue --issue "fix/<shortFixName>"
    ```
    Return `status=CANCELLED`

Do NOT proceed to STEP 5 until the user explicitly selects `Plan Approved`.

---

## STEP 5 — Promote temp repro to permanent integration test

Before writing the permanent test, confirm the assertion targets the right layer:

| Bug class | Assert on |
|-----------|-----------|
| host-only | host-side return values, files, CLI stdout/exit code |
| host→container boundary | in-container state via `podman exec` (env, files, command output) |
| in-container | command output from `podman exec <container> <cmd>` |

Determine the target integration test file from the bug's affected module:
- `terminal/`  → `tests/integration/test_terminal.py`
- `container/` → `tests/integration/test_container.py`
- `config/`    → `tests/integration/test_config.py`
- `integrations/` → `tests/integration/test_<service>.py`

Test function name: `test_<shortFixName_underscored>_regression`
(replace hyphens with underscores, e.g. `test_container_attach_leak_regression`)

Write the test using the docstring template from:
`.claude/commands/tdd-issue/assets/test-docstring-template.py`

Required: `@pytest.mark.integration` decorator.

If target file exists, append the test. If not, create it with appropriate imports.

After writing the test, delete `tests/temp_repro.py`:
```bash
rm /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/tests/temp_repro.py
```

Run the integration test to confirm still RED using the test output pattern with `<step>=step5`:

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/test-step5-${TIMESTAMP}.log"
cd /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName> && \
  PYTHONPATH=/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src \
  uv run pytest tests/integration/test_<area>.py::test_<name>_regression \
    -q --tb=short -p no:cov --override-ini="addopts=" 2>&1 | tee "$LOG_FILE"
echo ""
echo "--- Test summary (full output: $LOG_FILE) ---"
grep -E "^(FAILED|ERROR|E |AssertionError|====)" "$LOG_FILE" | head -25
```

> **Docstring trap:** Write Expected/Actual in terms of *observable behaviour*, not current API
> call signatures. If the fix inverts a flag, the docstring must describe the end-user behaviour,
> not the flag value.

Update tracking:
```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action add-integration-test \
  --issue "fix/<shortFixName>" \
  --test-function "test_<name>_regression" \
  --test-file "tests/integration/test_<area>.py" \
  --status RED
```

---

## End of phase — Update resume state

Update `/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/resume.md`:

```markdown
---
completed_phases: [setup, red]
current_phase: green
---

## State

short_fix_name: <shortFixName>
bug_class: <bugClass>
repro_summary: <reproSummary>
error_message: <errorMessage>
severity: <severity>
source: <source>
integration_test_file: tests/integration/test_<area>.py
integration_test_function: test_<name>_regression
```

---

## Output

**On success:**
```json
{
  "phase": "red",
  "status": "DONE",
  "shortFixName": "<shortFixName>",
  "integrationTestFile": "tests/integration/test_<area>.py",
  "integrationTestFunction": "test_<name>_regression",
  "details": "Integration test RED confirmed. Ready for investigation and fix."
}
```

**On CANCELLED (user said no at STEP 4.5):**
```json
{
  "phase": "red",
  "status": "CANCELLED",
  "shortFixName": "<shortFixName>",
  "integrationTestFile": "",
  "integrationTestFunction": "",
  "details": "Issue cancelled by user at sanity check. Worktree removed, issue closed."
}
```
