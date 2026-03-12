# Unit Test Agent — TDD Issue Sub-Agent

This file is the prompt template for unit test sub-agents spawned by the tdd-issue orchestrator.
Each agent handles one source file: write unit test RED → fix src to GREEN → refactor → merge back.

---

## Variables passed by orchestrator

| Variable | Description |
|---|---|
| `issue_branch` | e.g. `fix/container-attach-leak` |
| `src_file` | e.g. `src/mc/terminal/attach.py` |
| `issue_summary` | One sentence description of the bug |
| `unit_test_name` | e.g. `test-attach-fd-cleanup` |
| `backwards_compat` | `true` or `false` |
| `repo_root` | `/Users/dsquirre/Repos/mc` |

---

## STEP A — Create unit test worktree + branch

Create a nested branch from the issue branch (not from main):

```bash
cd {repo_root} && bash .claude/commands/tdd-issue/scripts/create-worktree.sh \
  "fix/{issue_branch_name}--{unit_test_name}"
```

Where `{issue_branch_name}` is the short name portion — if `issue_branch` is
`fix/container-attach-leak`, then `{issue_branch_name}` is `container-attach-leak`.

Full branch created: `fix/<shortFixName>--<unit_test_name>` (double-dash separator — avoids git ref/file conflict)
Full worktree created: `.tdd/worktrees/fix/<shortFixName>/<unit_test_name>` (slash separator — directory nesting is fine)

> **Note:** Each Bash call resets CWD. Always use `cd /absolute/path && <command>` in a single call.

**All work happens inside this worktree from this point forward.**

---

## STEP B — Write unit test in RED (Prosecutor)

Read the source file to understand current implementation:
```bash
# Read the source file from the worktree
# Path: .tdd/worktrees/fix/<shortFixName>/<unit_test_name>/{src_file}
```

Locate or create the unit test file:
- Convention: `tests/unit/test_<module_name>.py`
- Example: `src/mc/terminal/attach.py` → `tests/unit/test_attach.py`
- If the file exists, append to it. If not, create it.

Write a focused unit test that:
- Targets the specific broken behaviour described in `{issue_summary}`
- Tests only the behaviour of `{src_file}` (mock external dependencies)
- Has a descriptive name: `test_<specific_scenario>_<expected_outcome>`
- Will FAIL when the bug is present

If `{backwards_compat}` = `true`:
- Add `@pytest.mark.backwards_compatibility` to the test
- This signals the test covers a public API contract

> **Worktree pytest note:** Use `-p no:cov` (not `--no-cov`) to disable the coverage plugin
> entirely — `--no-cov` suppresses the report but still lets pytest-cov redirect imports away
> from the worktree's `src/`. Also add `--override-ini="addopts="` to prevent `pyproject.toml`'s
> `addopts` from injecting coverage flags that conflict with `-p no:cov`. Set `PYTHONPATH`
> explicitly so Python resolves `mc` from the worktree source tree, not the main repo's editable
> install `.pth` redirect. Each Bash call resets CWD — always use `cd /absolute/path && <command>`
> in a single call.

> **Assertion guidance:** When testing functions that return dicts or lists that may include
> environment-specific paths (e.g. `~/Library/Application Support/ocm/ocm.json` which only
> exists on some machines), use partial assertions rather than full dict equality:
> - Prefer: `assert expected_key in result` or `assert result[key] == expected_value`
> - Avoid: `assert result == {full_expected_dict}` — breaks on machines where optional paths exist
> - Alternative: mock the path-resolution function (e.g. `get_ocm_config_path`) to return a stable test path

Run the test and assert FAIL (RED):
```bash
cd {repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name> && PYTHONPATH={repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name>/src uv run pytest tests/unit/test_<module>.py::<test_name> -v -s -p no:cov --override-ini="addopts="
```

IF test passes immediately:
- The test does not target the broken behaviour — revise it
- Re-examine `{issue_summary}` and `{src_file}` to find the right assertion
- Do NOT proceed until the test FAILS

Update tracking:
```bash
cd {repo_root} && bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action update-unit-test \
  --issue "{issue_branch}" \
  --unit-test "{unit_test_name}" \
  --status RED
```

---

## STEP C — Fix the source file to GREEN (Surgeon)

Modify `{src_file}` only — minimum change to fix the root cause.

Rules:
- No unrelated refactoring
- No phantom logic (changes not required by the test)
- No changes to files other than `{src_file}` and the test file

Run the unit test:
```bash
cd {repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name> && PYTHONPATH={repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name>/src uv run pytest tests/unit/test_<module>.py::<test_name> -v -s -p no:cov --override-ini="addopts="
```

IF RED:
- Fix is incomplete or incorrect
- Adjust implementation
- Re-run test
- Loop (max {UNIT_AGENT_MAX_RETRIES} = 5 attempts)
- After 5 failed attempts: signal BLOCKED (see OUTPUT section below)

IF GREEN: proceed to STEP D.

---

## STEP D — Refactor (Inspector)

Clean up the implementation if needed:
- Improve naming, remove duplication, simplify logic
- No behaviour changes — the test must still pass after refactoring

Run the unit test to confirm still GREEN:
```bash
cd {repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name> && PYTHONPATH={repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name>/src uv run pytest tests/unit/test_<module>.py::<test_name> -v -p no:cov --override-ini="addopts="
```

Run the full unit suite to check for regressions:
```bash
cd {repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name> && PYTHONPATH={repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name>/src uv run pytest tests/unit/ -v -p no:cov --override-ini="addopts=" -q
```

If any regressions: fix them before proceeding.

---

## STEP E — Commit, merge back, and clean up

Commit inside the unit test worktree:
```bash
cd {repo_root}/.tdd/worktrees/fix/<shortFixName>/<unit_test_name> && \
git add {src_file} tests/unit/test_<module>.py && \
git commit -m "$(cat <<'EOF'
fix(<module>): <what was fixed — one line>

Unit test: test_<name>
Part of: {issue_branch}
Root cause: <one sentence>

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

Merge the unit test branch back into the issue branch:
```bash
cd {repo_root} && bash .claude/commands/tdd-issue/scripts/cleanup-worktree.sh \
  "fix/<shortFixName>--<unit_test_name>" \
  --merge-into "{issue_branch}"
```

This script:
1. Removes worktree `.tdd/worktrees/fix/<shortFixName>/<unit_test_name>`
2. Merges `fix/<shortFixName>--<unit_test_name>` into `{issue_branch}` with `--no-ff`
3. Deletes branch `fix/<shortFixName>--<unit_test_name>`

If merge has conflicts: abort, report BLOCKED. Do NOT force.

Update tracking:
```bash
cd {repo_root} && bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action update-unit-test \
  --issue "{issue_branch}" \
  --unit-test "{unit_test_name}" \
  --status MERGED
```

---

## OUTPUT

Return this JSON to the orchestrator (STEP 9):

**On success:**
```json
{
  "status": "GREEN",
  "unit_test_name": "{unit_test_name}",
  "src_file": "{src_file}",
  "test_file": "tests/unit/test_<module>.py",
  "commit_sha": "<7-char sha>",
  "details": "<one sentence: what was fixed and how>"
}
```

**On failure (BLOCKED after 5 attempts or merge conflict):**
```json
{
  "status": "BLOCKED",
  "unit_test_name": "{unit_test_name}",
  "src_file": "{src_file}",
  "test_file": "tests/unit/test_<module>.py",
  "commit_sha": null,
  "details": "<what was tried, what is blocking, what the orchestrator should investigate>"
}
```
