# Phase: Setup — Detective (STEP 0a, 0b, 0d, 1, 2)

This file is executed by a sub-agent spawned by the tdd-issue orchestrator.
Read it fully before taking any action.

---

## Variables passed by orchestrator

| Variable | Description |
|---|---|
| `repo_root` | `/Users/dsquirre/Repos/mc` |
| `resume_context` | Contents of resume.md if resuming, otherwise empty string |

---

## On resume

If `resume_context` is non-empty AND it contains `completed_phases: [setup]` or lists "setup" in
completed_phases, skip ALL steps below and return immediately:

```json
{
  "phase": "setup",
  "status": "DONE",
  "shortFixName": "<from resume_context short_fix_name>",
  "bugClass": "<from resume_context bug_class>",
  "reproSummary": "<from resume_context repro_summary>",
  "errorMessage": "<from resume_context error_message>",
  "details": "Resumed from saved state — setup phase already complete"
}
```

---

## STEP 0a — Verify `main` branch exists

```bash
git -C /Users/dsquirre/Repos/mc branch --list main
```

If output is empty (main branch does not exist), STOP immediately and return:

```json
{
  "phase": "setup",
  "status": "BLOCKED",
  "shortFixName": "",
  "details": "ERROR: `main` branch not found in repo. Cannot create a fix without a main branch."
}
```

The repo's current branch does NOT need to be `main` — parallel tdd-issue sessions each
work in their own git worktree, so the main repo can be on any branch.

## STEP 0b — Run bootstrap

```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/bootstrap.sh
```

## STEP 0d — Pre-flight test run

Run the full test suite against `main` using a temporary worktree so the current branch is irrelevant:

```bash
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
PREFLIGHT_DIR="/tmp/tdd-preflight-${TIMESTAMP}"
LOG_FILE="/tmp/tdd-preflight-${TIMESTAMP}.log"
git -C /Users/dsquirre/Repos/mc worktree add "$PREFLIGHT_DIR" main
cd "$PREFLIGHT_DIR"
uv run pytest tests/unit/ tests/integration/ -q --tb=short 2>&1 | tee "$LOG_FILE"
git -C /Users/dsquirre/Repos/mc worktree remove --force "$PREFLIGHT_DIR"
echo ""
echo "--- Pre-flight summary (full output: $LOG_FILE) ---"
grep -E "^(FAILED|ERROR|E |AssertionError|====)" "$LOG_FILE" | head -25
```

If all tests PASS → proceed to STEP 1.

If any tests FAIL → STOP and return:

```json
{
  "phase": "setup",
  "status": "BLOCKED",
  "shortFixName": "",
  "details": "PRE-FLIGHT FAILURE — <N> tests failing on main. Resolve these before starting a new issue. See log: <LOG_FILE>"
}
```

---

## STEP 1 — Interactive intake

Ask all questions at once if possible using AskUserQuestion:

1. What is broken? *(required — description of the bug)*
2. What did you expect to happen vs what actually happened?
3. Severity: critical / major / minor
4. Source: UAT ref / ticket number / ad-hoc
5. Can you reproduce it manually? What are the steps?

After collecting responses:
- Derive `<shortFixName>` from the description — lowercase, hyphenated, 2–5 words
  Example: "Container attach leaks file descriptors" → `container-attach-leak`
- Confirm with user: "I'll use `fix/container-attach-leak` — confirm or override?"

You have enough context to proceed when you know:
- Bug description
- Reproduction steps (at minimum a conceptual trace)
- Affected area of the codebase

---

## STEP 2 — Reproduce the bug

Before running anything, classify where the bug manifests:

| Class | Description | Example symptoms |
|-------|-------------|-----------------|
| **host-only** | Entirely on the host — CLI parsing, config management, case listing | Wrong exit code, bad output, missing file on host |
| **host→container boundary** | Host generates something consumed by the container | Env var missing in container shell, wrong file content in container |
| **in-container** | A tool or command running *inside* the container misbehaves | `ocm`/`backplane` fails, in-container `mc` command wrong |

Record your classification:
```
Bug class: <host-only | host→container boundary | in-container>
Reason: <one sentence>
```

Run bash commands to observe the failure live:

For **host-only** CLI bugs:
```bash
cd /Users/dsquirre/Repos/mc && uv run mc <relevant command> 2>&1
```

For **host-only** code-path bugs:
```bash
cd /Users/dsquirre/Repos/mc
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="/tmp/tdd-repro-${TIMESTAMP}.log"
uv run pytest tests/ -k "<relevant keyword>" -q --tb=short -p no:cov --override-ini="addopts=" 2>&1 | tee "$LOG_FILE"
grep -E "^(FAILED|ERROR|E |AssertionError|====)" "$LOG_FILE" | head -25
echo "Full output: $LOG_FILE"
```

For **host→container boundary** bugs:
```bash
podman exec <container_name> env | grep HTTPS_PROXY
podman exec <container_name> cat <path/to/file>
```

For **in-container** bugs:
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

> **Auth/config guard note:** If the CLI exits early due to a config guard, you cannot observe
> the bug live. Fall back to source code inspection. If the logic inversion or bug is unambiguous
> from reading the code, that is sufficient to proceed. Document what you read and why.

---

## End of phase — Write resume state

Create the per-issue state directory and write resume.md to the **main repo** (not inside any worktree):

```bash
mkdir -p /Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>
```

Write `/Users/dsquirre/Repos/mc/.tdd/issues/<shortFixName>/resume.md`:

```markdown
---
completed_phases: [setup]
current_phase: red
---

## State

short_fix_name: <shortFixName>
bug_class: <host-only | host→container boundary | in-container>
repro_summary: <one sentence>
error_message: <exact error captured>
severity: <critical|major|minor>
source: <UAT ref / ticket / ad-hoc>
```

---

## Output

Return this JSON to the orchestrator:

```json
{
  "phase": "setup",
  "status": "DONE",
  "shortFixName": "<name>",
  "bugClass": "<host-only|host→container boundary|in-container>",
  "reproSummary": "<one sentence>",
  "errorMessage": "<exact error>",
  "severity": "<critical|major|minor>",
  "source": "<source>",
  "details": "Bug reproduced. Class: <bugClass>. Error: <errorMessage>"
}
```
