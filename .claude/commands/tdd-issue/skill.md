---
name: tdd-issue
description: Fix a bug using TDD — red/green/refactor with parallel worktrees and issue tracking
argument-hint: "optional: shortFixName"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
---

<context>
@.claude/commands/tdd-issue/references/tdd-principles.md
@.claude/commands/tdd-issue/references/agent-tdd-workflow.md
@docs/INTEGRATION_TEST_BEST_PRACTICES.md
</context>

<configuration>
REPO_ROOT: /Users/dsquirre/Repos/mc
TRACKING_FILE: .tdd/issues/ISSUE_TRACKING.md
WORKTREE_BASE: .tdd/worktrees
MAX_PARALLEL_UNIT_AGENTS: 5
UNIT_AGENT_MAX_RETRIES: 5
</configuration>

<objective>
Fix a bug using strict Red-Green-Refactor TDD discipline:

1. Interactively gather enough context to write an integration test
2. Prove the bug exists with a failing temp repro test (explicit RED checkpoint)
3. Promote to a permanent integration test in tests/integration/
4. Investigate root cause, spawn parallel unit test agents per source file
5. Drive all agents to GREEN, then verify integration test is GREEN
6. Merge and close — tracked in .tdd/issues/ISSUE_TRACKING.md throughout

Each issue lives in its own git worktree. Multiple issues can run concurrently.
</objective>

<process>

<step name="bootstrap">
**STEP 0 — Bootstrap** (runs silently before anything else)

Run the bootstrap script to initialise .tdd/ directory structure:

```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/bootstrap.sh
```

After bootstrap:
- Read `.tdd/issues/ISSUE_TRACKING.md`
- If any issues have status = IN_PROGRESS, display them:
  ```
  Active issues in progress:
    - fix/<name> — <description> [status: IN_PROGRESS]
  ```
  Ask: "Would you like to resume one of these, or start a new issue?"
  - Resume → jump to the appropriate step based on last known status in the tracking file
  - New → continue to STEP 1
</step>

<step name="intake">
**STEP 1 — Interactive intake** (ask until you have enough to write the integration test)

Ask all at once if possible:

1. What is broken? *(required — description of the bug)*
2. What did you expect to happen vs what actually happened?
3. Severity: critical / major / minor
4. Source: UAT ref / ticket number / ad-hoc
5. Can you reproduce it manually? What are the steps?

After collecting responses:
- Derive `<shortFixName>` from the description — lowercase, hyphenated, 2–5 words
  Example: "Container attach leaks file descriptors" → `container-attach-leak`
- Present the derived name: "I'll use `fix/container-attach-leak` — confirm or override?"

You have enough context to proceed autonomously when you know:
- Bug description
- Reproduction steps (at minimum a conceptual trace)
- Affected area of the codebase

Transition message:
```
Intake complete. Proceeding autonomously.
Issue: fix/<shortFixName>
```
</step>

<step name="reproduce">
**STEP 2 — Reproduce the bug** (autonomous from here)

Before running anything, classify where the bug manifests — this determines how you reproduce
it and what the integration test must verify:

| Class | Description | Example symptoms |
|-------|-------------|-----------------|
| **host-only** | Entirely on the host — CLI parsing, config management, case listing | Wrong exit code, bad output, missing file on host |
| **host→container boundary** | Host generates something (bashrc, mount flags, env vars) consumed by the container | Env var missing in container shell, wrong file content in container |
| **in-container** | A tool or command running *inside* the container misbehaves | `ocm`/`backplane` fails, in-container `mc` command wrong |

Record your classification before proceeding:
```
Bug class: <host-only | host→container boundary | in-container>
Reason: <one sentence>
```

Run bash commands to observe the failure live using the reproduction steps from intake.

For **host-only** CLI bugs:
```bash
cd /Users/dsquirre/Repos/mc
uv run mc <relevant command> 2>&1
```

For **host-only** code-path bugs, run related tests to see failure surface:
```bash
cd /Users/dsquirre/Repos/mc && uv run pytest tests/ -k "<relevant keyword>" -v -p no:cov --override-ini="addopts=" -s 2>&1
```

For **host→container boundary** bugs, reproduction must show the failure *inside* the container,
not just in the host-side code that generates the artifact:
```bash
# Start a container for the case (or use an existing one)
podman exec <container_name> env | grep HTTPS_PROXY        # env var missing
podman exec <container_name> cat <path/to/file>            # file wrong or absent
podman exec <container_name> bash -c "source <file> && echo $VAR"  # sourcing fails
```

For **in-container** bugs, exec the failing command directly:
```bash
podman exec <container_name> <failing-command> 2>&1
```

Capture exactly:
- Error message
- Stack trace
- Unexpected output vs expected output

IF cannot reproduce:
- Return to interactive — tell the user what you tried
- Ask for more specific reproduction steps
- Do NOT proceed until the failure is observed

> **Auth/config guard note:** If the CLI itself exits early due to a config guard (e.g. legacy
> env var detection, missing TOML config, or auth token check), you cannot observe the bug live.
> This is acceptable — fall back to source code inspection to confirm the root cause. If the logic
> inversion or bug is unambiguous from reading the code, that is sufficient to proceed. Document
> what you read and why you concluded the bug is present.

Confirm reproduction:
```
Bug reproduced.
Error: <exact error>
Trace: <key frame>
```
</step>

<step name="create_worktree">
**STEP 3 — Create issue worktree + branch**

```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/create-worktree.sh fix/<shortFixName>
```

This creates:
- Branch: `fix/<shortFixName>` (from main)
- Worktree: `.tdd/worktrees/fix/<shortFixName>`

All subsequent orchestrator file-editing work happens inside the worktree path.

Add the issue to the tracking file:
```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action add-issue \
  --issue "fix/<shortFixName>" \
  --description "<one sentence bug description>" \
  --severity "<critical|major|minor>" \
  --source "<UAT ref / ticket / ad-hoc>"
```
</step>

<step name="temp_repro">
**STEP 4 — Write temp repro test** (Detective / Prosecutor)

This is the explicit "prove it" gate. Do NOT touch source code yet.

Create `tests/temp_repro.py` inside the issue worktree:
```
.tdd/worktrees/fix/<shortFixName>/tests/temp_repro.py
```

Requirements:
- Minimal pytest test that triggers the exact bug
- Uses real components (do not mock the thing being tested)
- Has a clear assertion that FAILS when the bug is present
- Has a comment explaining why it should fail

**Verification depth — match the test to the bug class from STEP 2:**

- **host-only** — assert on host-side state: return values, files on disk, CLI stdout/exit code.
  No container needed.

- **host→container boundary** — the test MUST verify the end state inside a real container.
  Asserting on the Python object that was *supposed* to produce the artifact is not enough.
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
  ```python
  result = subprocess.run(
      ["podman", "exec", container_name, "<failing-command>"],
      capture_output=True, text=True,
  )
  assert expected_output in result.stdout
  ```

> **Trap to avoid:** For host→container and in-container bugs, do NOT write a test that only
> checks an intermediate Python value (a string return, a dict, a generated file path).  If the
> test can pass without a container running, it is almost certainly testing at the wrong depth.

> **Worktree pytest note:** Each Bash call resets CWD — always use `cd /absolute/path && command`
> in a single call. Use `-p no:cov` (not `--no-cov`) to disable the coverage plugin entirely;
> `--no-cov` suppresses the report but still lets pytest-cov hijack imports from the main repo.
> Also add `--override-ini="addopts="` to prevent `pyproject.toml`'s `addopts` from injecting
> coverage flags that conflict with `-p no:cov`. Set `PYTHONPATH` to the worktree's `src/` so
> Python resolves `mc` from the worktree source tree, not the main repo's editable install
> `.pth` redirect.

Run it and assert FAIL (RED):
```bash
cd /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName> && PYTHONPATH=/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src uv run pytest tests/temp_repro.py -v -s -p no:cov --override-ini="addopts="
```

IF test PASSES immediately:
- The test does not reproduce the bug — revise it
- Do NOT proceed until the test FAILS

Display RED confirmation:
```
RED confirmed: tests/temp_repro.py FAILS as expected.
Error: <exact failure message>
```
</step>

<step name="sanity_check">
**STEP 4.5 — Sanity check (human gate)**

Before writing any permanent test or touching any source file, present a structured
brief to the user and wait for explicit approval.

Format:

```
BUG BRIEF — fix/<shortFixName>
═══════════════════════════════════════════════════════════
Bug class    : <host-only | host→container boundary | in-container>
Reproduced   : YES — <exact error from RED test, one line>
Root cause   : <one sentence, file:line if known>
Confidence   : <HIGH | MEDIUM | LOW>  (<reason if not HIGH>)
Unknowns     : <none | list any open questions>

Fix plan
───────────────────────────────────────────────────────────
  Source files to change:
    - <src_file>:<line> — <what changes>
  Tests to add/update:
    - <integration test name> in tests/integration/<file>.py
    - <unit test name(s)> if applicable

On approval, next actions:
  1. Write failing integration test (permanent RED)
  2. Fix <src_file>
  3. Update any existing tests asserting wrong behaviour
  4. Verify integration test GREEN
  5. Merge fix/<shortFixName> to main
═══════════════════════════════════════════════════════════
Proceed? [yes / no / revise]
```

**Response handling:**

- `yes` → delete `tests/temp_repro.py`, proceed to STEP 5
- `no`  → delete `tests/temp_repro.py`, clean up worktree, close issue as CANCELLED
           in tracking, stop
- `revise <correction>` → incorporate the correction into the brief and fix plan,
           re-present (loop until `yes` or `no`)

Do NOT proceed to STEP 5 until the user explicitly types `yes`.
</step>

<step name="promote_test">
**STEP 5 — Promote temp repro to permanent integration test**

Before writing the permanent test, state the bug class (from STEP 2) and confirm the assertion
targets the right layer:

| Bug class | Assert on |
|-----------|-----------|
| host-only | host-side return values, files, CLI stdout/exit code |
| host→container boundary | in-container state via `podman exec` (env, files, command output) |
| in-container | command output from `podman exec <container> <cmd>` |

If the bug class is **host→container boundary** or **in-container**, the test MUST require a
running container. Add `@pytest.mark.skipif(not _podman_available(), reason="Podman required")`
and create/clean up the container in the test body.

Determine the target integration test file from the bug's affected module:
- `terminal/`  → `tests/integration/test_terminal.py`
- `container/` → `tests/integration/test_container.py`
- `config/`    → `tests/integration/test_config.py`
- `integrations/` → `tests/integration/test_<service>.py`
- When in doubt: use the most semantically relevant existing integration test file

Test function name: `test_<shortFixName_underscored>_regression`
(replace hyphens with underscores, e.g. `test_container_attach_leak_regression`)

Write the test using the docstring template from:
`.claude/commands/tdd-issue/assets/test-docstring-template.py`

Required docstring fields:
- Bug description
- Steps to reproduce
- **Expected behaviour** (describe what the system *should* do — not the specific API call)
- **Actual behaviour** (describe what the system *actually* does when the bug is present)
- Source ref (UAT / ticket / date)
- `Bug discovered: YYYY-MM-DD`

> **Docstring trap:** Write the Expected/Actual fields in terms of *observable behaviour*,
> not the current API call signature. Hardcoding `launch=True` or other flag values in the
> docstring embeds the broken semantics — if the fix inverts a flag, the docstring becomes
> misleading. Instead write: "Expected: passing `-l` should open the URL in a browser" /
> "Actual: passing `-l` suppresses the browser and only prints the URL."

Required decorator: `@pytest.mark.integration`

If the target integration test file already exists, append the new test function.
If it does not exist, create it with appropriate imports.

After writing the test, delete `tests/temp_repro.py`:
```bash
rm /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/tests/temp_repro.py
```

Run the integration test to confirm still RED:
```bash
cd /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName> && PYTHONPATH=/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src uv run pytest tests/integration/test_<area>.py::test_<name>_regression -v -p no:cov --override-ini="addopts="
```

Update tracking:
```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action add-integration-test \
  --issue "fix/<shortFixName>" \
  --test-function "test_<name>_regression" \
  --test-file "tests/integration/test_<area>.py" \
  --status RED
```
</step>

<step name="investigate">
**STEP 6 — Investigate root cause** (Detective)

From inside the issue worktree, read the source files implicated by the stack trace
and the failing integration test.

Trace the execution path:
1. What does the integration test call?
2. Which functions are invoked?
3. Where does the failure originate?
4. What is the root cause?

Use Read in parallel for multiple source files.
Use Grep to locate specific patterns or callsites.

Document findings before moving on:
```
Root cause: <one sentence>

Affected source files:
  - src/mc/<module1>.py:<line> — <what is wrong here>
  - src/mc/<module2>.py:<line> — <what is wrong here>
```
</step>

<step name="triage">
**STEP 7 — Triage source files**

For each affected source file, make a decision:

**DECISION: Does this src_file need a new or updated unit test?**

YES (needs a unit test) →
  - Assign a `<unitTestName>`: lowercase, hyphenated, starts with `test-`
    Example: `test-attach-fd-cleanup`
  - Check: does this change touch a public API method?
    - YES → set `backwards_compat = true` for the agent
  - Queue for UNIT TEST AGENT (STEP 8)
  - Add to tracking:
    ```bash
    bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
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
</step>

<step name="spawn_agents">
**STEP 8 — Spawn unit test agents in parallel**

For each queued src_file, spawn one Task using the unit-test-agent template.
Maximum MAX_PARALLEL_UNIT_AGENTS (5) concurrent agents.

> **Permission pre-flight:** Sub-agents need Bash tool access to run tests and git commands.
> When Claude Code prompts you to approve tool use for a spawned agent, **approve Bash** (and
> Read/Write/Edit/Glob/Grep if asked). Without Bash the agent will stall after writing the test
> file and cannot complete the RED→GREEN→commit→merge cycle autonomously.

Spawn all agents before waiting for any:

```
Task(
  subagent_type="general-purpose",
  description="Unit test agent: fix/<shortFixName>--<unitTestName>",
  allowed_tools=["Bash", "Read", "Write", "Edit", "Glob", "Grep"],
  prompt="""
Read and follow the instructions at:
  /Users/dsquirre/Repos/mc/.claude/commands/tdd-issue/agents/unit-test-agent.md

Variables for this run:
  issue_branch:   fix/<shortFixName>
  src_file:       <src_file>
  issue_summary:  <one sentence description of the bug>
  unit_test_name: <unitTestName>
  backwards_compat: <true|false>
  repo_root:      /Users/dsquirre/Repos/mc
""",
  run_in_background=True
)
```

After spawning all agents, proceed immediately to STEP 9.
</step>

<step name="wait_and_track">
**STEP 9 — Wait for agent results and track**

Use TaskOutput to collect results from each agent as they complete.
Parse the JSON output from each agent (see unit-test-agent.md for schema).

For each GREEN result:
```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action update-unit-test \
  --issue "fix/<shortFixName>" \
  --unit-test "<unitTestName>" \
  --status MERGED
```

For each BLOCKED result:
- Read the agent's `details` field to understand the blocker
- Investigate the source file and the test directly
- Resolve the issue (edit source or test), then either:
  - Re-run the agent for that unit test, or
  - Fix it directly in the worktree

Display live status as agents report:
```
Unit test agents (fix/<shortFixName>):
  - test-attach-fd-cleanup:   GREEN (merged)
  - test-state-gc-cleanup:    in progress...
  - test-config-reload:       BLOCKED — see details
```
</step>

<step name="integration_green">
**STEP 10 — Run the integration test**

All unit test branches should now be merged into `fix/<shortFixName>`.

Run the integration test from inside the issue worktree:
```bash
cd /Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName> && PYTHONPATH=/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>/src uv run pytest tests/integration/test_<area>.py::test_<name>_regression -v -s -p no:cov --override-ini="addopts="
```

> **Post-fix assertion review:** Before running the integration test here, re-read the test's
> assertions in light of the fix. If the fix inverted a flag or changed an API call's semantics,
> the assertions written during STEP 5 (RED) may now be testing the wrong condition. Verify that:
> - The assertion reflects the *correct post-fix behaviour*, not the pre-fix broken state
> - The test would still fail if you reintroduce the bug
> If the assertion is wrong, fix it now — this is not a new RED/GREEN cycle, it is correcting
> a mis-stated expectation before validating the full fix.

IF RED:
- Unit tests are green but integration still fails
- Something deeper was missed — multi-file interaction or uncovered code path
- Return to STEP 6 (re-investigate)
- Do NOT merge until GREEN
- Genuinely re-read and re-analyse — do NOT retry the same fix

IF GREEN:
```
Integration test GREEN: test_<name>_regression PASSED
Proceeding to merge.
```

Update tracking:
```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action update-integration-test \
  --issue "fix/<shortFixName>" \
  --test-function "test_<name>_regression" \
  --status GREEN
```
</step>

<step name="merge_and_close">
**STEP 11 — Merge and close**

Run the cleanup script:
```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/cleanup-worktree.sh \
  "fix/<shortFixName>" --merge-into main
```

This script:
1. Removes worktree `.tdd/worktrees/fix/<shortFixName>`
2. Merges `fix/<shortFixName>` into `main` with `--no-ff`
3. Deletes branch `fix/<shortFixName>`

IF merge has conflicts: the script aborts and reports. Do NOT force-merge.
Resolve conflicts manually, commit, then re-run cleanup.

After successful merge, close the issue in tracking:
```bash
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action close-issue \
  --issue "fix/<shortFixName>"
```

Final summary:
```
Issue fix/<shortFixName> complete.

Integration test : GREEN (test_<name>_regression)
Unit tests fixed : <N>
Merged to main   : <commit sha>

See .tdd/issues/ISSUE_TRACKING.md for full history.
```
</step>

</process>

<output>
- Bug reproduced and confirmed with a failing integration test (RED before fix)
- Root cause identified and fixed at the source
- Permanent regression test in tests/integration/test_<area>.py
- Unit tests for each changed source file (coverage maintained)
- All tests GREEN before merging
- Issue tracked in .tdd/issues/ISSUE_TRACKING.md from intake through DONE
- Clean no-ff merge to main with no regressions
</output>

<anti_patterns>
- Do NOT touch source code before the temp repro test confirms RED (STEP 4 is the gate)
- Do NOT move to integration test step until temp_repro.py FAILS
- Do NOT merge to main until the integration test is GREEN (STEP 10)
- Do NOT mock the thing being tested in integration tests
- Do NOT write a host-only assertion for a host→container boundary or in-container bug — if the test can pass without a container running, it is testing at the wrong depth
- Do NOT retry the same fix approach in the STEP 10 RED loop — genuinely re-investigate
- Do NOT spawn more than 5 unit test agents concurrently
- Do NOT skip the backwards_compat flag for public API changes
- Do NOT force-merge on conflicts — resolve them properly

**Host→container boundary traps (learned from proxy detection bug, 2026-03-11):**

- Do NOT assert on an intermediate Python return value (a dict, a string, a generated file
  path) for host→container boundary bugs. The fix may be at a different layer than where
  the artifact is generated.
  ```
  # BAD — tests the wrong layer
  bashrc = generate_bashrc(case_number, metadata)
  assert "HTTPS_PROXY" in bashrc   # passes even if the shell never sees the var

  # GOOD — tests the actual in-container result
  result = subprocess.run(
      ["podman", "exec", "--env", f"HTTPS_PROXY={proxy}", container, "bash", "-c", "echo $HTTPS_PROXY"],
      capture_output=True, text=True,
  )
  assert result.stdout.strip() == proxy
  ```

- Do NOT assume that writing a value into a file (bashrc, config) guarantees it reaches
  the running process. Shell startup files have loading rules (BASH_ENV = non-interactive
  only; ~/.bashrc = interactive non-login; ~/.bash_profile = login). Test that the value
  reaches the process that actually needs it — via `podman exec env`, `podman exec bash -c
  'echo $VAR'`, or equivalent.

- Do NOT diagnose a host→container boundary bug by only reading host-side source code.
  Always confirm with a live `podman exec` command that shows the failure inside the
  container before writing the integration test.
</anti_patterns>

<success_criteria>
- [ ] STEP 0: .tdd/ structure created, .gitignore updated, tracking file seeded
- [ ] STEP 1: All 5 intake questions answered, shortFixName confirmed by user
- [ ] STEP 2: Bug reproduced live with exact error captured
- [ ] STEP 3: Worktree and branch created, issue added to tracking (IN_PROGRESS)
- [ ] STEP 4: tests/temp_repro.py FAILS — RED confirmed
- [ ] STEP 4.5: Bug brief presented, user approved with "yes" before any permanent test written
- [ ] STEP 5: Integration test in tests/integration/ FAILS — RED confirmed, temp file deleted
- [ ] STEP 6: Root cause identified with exact file and line
- [ ] STEP 7: Source files triaged — agents queued or inline fixes applied
- [ ] STEP 8: All agents spawned in parallel (max 5)
- [ ] STEP 9: All agents GREEN or BLOCKED resolved
- [ ] STEP 10: Integration test PASSES — GREEN confirmed
- [ ] STEP 11: Merged to main, worktree removed, issue status = DONE
</success_criteria>
