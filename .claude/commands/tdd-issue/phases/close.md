# Phase: Close — Inspector (STEP 11)

This file is executed by a sub-agent spawned by the tdd-issue orchestrator.
Read it fully before taking any action.

---

## Variables passed by orchestrator

| Variable | Description |
|---|---|
| `repo_root` | `/Users/dsquirre/Repos/mc` |
| `shortFixName` | e.g. `container-attach-leak` |
| `integrationTestFile` | e.g. `tests/integration/test_container.py` |
| `integrationTestFunction` | e.g. `test_container_attach_leak_regression` |
| `unitTestsFixed` | Number of unit tests fixed |

Derived constants:
- `issue_branch` = `fix/<shortFixName>`
- `worktree_path` = `/Users/dsquirre/Repos/mc/.tdd/worktrees/fix/<shortFixName>`

---

## STEP 11a — Remove the worktree, keep the branch

```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/cleanup-worktree.sh \
  "fix/<shortFixName>" --keep-branch
```

This removes the worktree at `.tdd/worktrees/fix/<shortFixName>` but leaves branch
`fix/<shortFixName>` intact in the primary repository.

---

## STEP 11b — Rebase the fix branch onto `main`

```bash
cd /Users/dsquirre/Repos/mc
git rebase main fix/<shortFixName>
```

If rebase has conflicts, STOP and return BLOCKED:

```json
{
  "phase": "close",
  "status": "BLOCKED",
  "shortFixName": "<shortFixName>",
  "branchName": "fix/<shortFixName>",
  "details": "REBASE CONFLICT on fix/<shortFixName>. Resolve manually then re-run /tdd-issue. Commands: git rebase --continue (after resolving each file) or git rebase --abort (to cancel)."
}
```

Do NOT proceed to STEP 11c until the rebase completes cleanly.

---

## STEP 11c — Mark issue as BRANCH_READY in tracking

```bash
cd /Users/dsquirre/Repos/mc
bash .claude/commands/tdd-issue/scripts/update-tracking.sh \
  --action promote-issue \
  --issue "fix/<shortFixName>"
```

---

## End of phase — Print final summary

```
Issue fix/<shortFixName> complete.

Integration test : GREEN (<integrationTestFunction>)
Unit tests fixed : <unitTestsFixed>
Branch           : fix/<shortFixName> (rebased onto main, ready for review)

The branch has NOT been merged to main.
Review and merge when ready:
  git checkout main && git merge --no-ff fix/<shortFixName>

See .tdd/issues/ISSUE_TRACKING.md for full history.
```

---

## Output

**On success:**
```json
{
  "phase": "close",
  "status": "DONE",
  "shortFixName": "<shortFixName>",
  "branchName": "fix/<shortFixName>",
  "details": "Branch fix/<shortFixName> rebased onto main and marked BRANCH_READY. Worktree removed."
}
```

**On rebase conflict (BLOCKED):**
```json
{
  "phase": "close",
  "status": "BLOCKED",
  "shortFixName": "<shortFixName>",
  "branchName": "fix/<shortFixName>",
  "details": "REBASE CONFLICT on fix/<shortFixName>. Resolve manually then re-run /tdd-issue."
}
```
