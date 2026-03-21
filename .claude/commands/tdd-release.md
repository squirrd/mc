---
name: tdd-release
description: Build a versioned release branch from selected fix/feat branches, run tests after each merge, and ship to GitHub.
argument-hint: "optional: minor-bump | major-bump (default: patch bump)"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Build a clean release by:
1. Suggesting the next version (patch by default; pass `minor-bump` or `major-bump` to override)
2. Listing all available branches (local + remote) for the user to select
3. Merging selected branches oldest-first into a new version branch, running the full test suite after each merge
4. Rolling back any branch that fails tests, logging the failure, and continuing with the remaining branches
5. Bumping the version in pyproject.toml, merging to main, tagging, and publishing the GitHub release
6. Cleaning up: deleting merged branches (local + remote), pushing any unselected local-only branches to remote
</objective>

<configuration>
REPO_ROOT: /Users/dsquirre/Repos/mc
RELEASE_LOG: .planning/release-log.md
GITHUB_REPO: squirrd/mc
TEST_CMD: bash scripts/release/run_tests.sh
</configuration>

---

## PHASE 0 — Setup

### 0a: Ensure main is current

```bash
git checkout main
git pull --ff-only origin main
```

If `pull --ff-only` fails (diverged), STOP and tell the user to resolve the divergence manually.

### 0b: Determine bump type

Check `$ARGUMENTS` for the words `minor-bump` or `major-bump`. Default is `patch`.

```bash
python3 scripts/release/suggest_version.py [patch|minor|major]
```

Store the result as VERSION (e.g. `2.0.9`). The version branch will be named `v{VERSION}`.

### 0c: Confirm version with user

Use **AskUserQuestion** with one question:

- Header: "Release version"
- Question: "The next version will be **v{VERSION}** (patch bump from latest tag). Accept or enter a custom version?"
- Options:
  - `v{VERSION}` — Use the suggested version (Recommended)
  - `Custom` — Enter a different version in the text field

If the user selects Custom, use the value they typed in Other as VERSION (strip any leading `v`).

---

## PHASE 1 — Branch Selection

### 1a: List available branches

```bash
python3 scripts/release/list_branches.py --exclude v{VERSION}
```

This fetches from remote (`git fetch --prune`) and prints a numbered list of all branches
sorted oldest → newest by last commit date, excluding `main`, `HEAD`, version branches, and the new version branch.

Print the full numbered list as output so the user can see it clearly.

### 1b: Ask user which branches to include

Call **AskUserQuestion** with one question:

- Header: "Branch selection"
- Question: "Which branches should be included in v{VERSION}? (branches will be merged oldest-first)"
- Options:
  - `All branches` — Include every branch listed above
  - `Select specific` — Type the branch numbers (e.g. `1,3,4`) in the text field
  - `All except some` — Type the numbers to EXCLUDE in the text field
  - `None` — Release current main as-is (no branch merges)

Parse the user's response:
- "All branches" → SELECTED = all branches from the list (in the order shown, oldest first)
- "Select specific" → parse the numbers from Other, pick those branches in listed order
- "All except some" → parse exclusion numbers from Other, remove those from the full list
- "None" → SELECTED = [] (skip Phase 2 entirely)

Store SELECTED_BRANCHES as an ordered list (oldest → newest).

---

## PHASE 2 — Create Version Branch

```bash
git checkout -b v{VERSION} main
```

Initialise tracking variables (mental state — track in your reasoning):
- `MERGED_BRANCHES = []`
- `FAILED_BRANCHES = []`

---

## PHASE 3 — Merge Loop

For **each branch** in SELECTED_BRANCHES (in order, oldest first):

### 3a: Ensure branch exists locally

If the branch is remote-only (has `origin/` prefix in the list output):

```bash
git checkout -b {branch} origin/{branch}
```

If already local, no action needed.

### 3b: Switch to version branch

```bash
git checkout v{VERSION}
```

### 3c: Merge the branch

```bash
git merge {branch} --no-edit
```

If the merge produces conflicts, do NOT attempt to resolve them automatically. Instead:
- Run `git merge --abort`
- Treat this as a test failure (skip to 3e)
- Log reason as: "Merge conflict — manual resolution required"

### 3d: Run the full test suite

```bash
bash scripts/release/run_tests.sh
```

**If tests PASS** (exit code 0):
- Add branch to MERGED_BRANCHES
- Print: `✅ {branch} merged and tested successfully`
- Continue to the next branch

**If tests FAIL** (non-zero exit):
- Continue to 3e

### 3e: Handle test failure

```bash
# Log the failure
python3 scripts/release/log_failure.py {VERSION} {branch} "Test suite failed after merge"

# Undo the merge (reset to before the merge commit)
git reset --hard HEAD~1
```

If the merge had a conflict and was aborted, skip the `git reset` step.

Add branch to FAILED_BRANCHES. Print:

```
❌ {branch} failed tests — rolling back and continuing without it.
   Logged to .planning/release-log.md
```

No need to rebuild the entire version branch — since we reset the merge, the version branch is clean again.

---

## PHASE 4 — Version Bump

On the version branch (`v{VERSION}`):

### 4a: Update pyproject.toml

Use the Edit tool to change:
```
version = "{current_version}"
```
to:
```
version = "{VERSION}"
```

### 4b: Verify

```bash
uv run mc --version
```

Output should show: `mc {VERSION}`

### 4c: Commit

```bash
git add pyproject.toml
git commit -m "chore: bump version to {VERSION}"
```

---

## PHASE 5 — Merge Version Branch to Main

```bash
git checkout main
git merge v{VERSION}
```

This should be a fast-forward since `v{VERSION}` was created from `main` tip.

If git reports "Already up to date" or a clean fast-forward, continue.

If a merge commit is required (main has diverged since the start), rebase the version branch first:

```bash
git checkout v{VERSION}
git rebase main
git checkout main
git merge v{VERSION}
```

---

## PHASE 6 — Tag and Publish

### 6a: Push main

```bash
git push origin main
```

### 6b: Create version tag and move latest

```bash
git tag v{VERSION}
git tag -f latest
git push origin v{VERSION}
git push origin latest --force
```

### 6c: Generate release notes

Read the commit messages for all commits on the version branch (between the previous version tag and HEAD):

```bash
git log v{PREV_VERSION}..v{VERSION} --oneline --no-merges
```

Where PREV_VERSION is the tag before the current one (`git tag --list 'v*' --sort=-version:refname | sed -n '2p'`).

Group the commits by prefix (feat/fix/chore/docs). Format as a clean `## What's New` section.

### 6d: Create GitHub release

```bash
gh release create v{VERSION} \
  --title "v{VERSION} — {short description based on merged branches}" \
  --notes "$(cat <<'NOTES'
{generated release notes}

## Install / Upgrade

\`\`\`bash
# Fresh install
uv tool install git+https://github.com/squirrd/mc@v{VERSION}

# Upgrade existing install
mc-update upgrade
\`\`\`
NOTES
)"
```

### 6e: Verify install

```bash
uv tool install --force "git+https://github.com/squirrd/mc@v{VERSION}"
mc --version
```

Confirm output is `mc {VERSION}`. If not, STOP and report the discrepancy.

---

## PHASE 7 — Cleanup

### 7a: Delete merged branches (local + remote)

For each branch in MERGED_BRANCHES:

```bash
git branch -D {branch}
git push origin --delete {branch}
```

If the branch has no remote (local-only), skip the `push --delete` step.

### 7b: Push unselected local-only branches to remote

Find local branches that were listed in Phase 1 but were NOT selected (i.e. not in SELECTED_BRANCHES and not in the excluded/skipped list):

```bash
git branch --list
```

For each such branch that has no remote tracking:

```bash
git push -u origin {branch}
```

This makes them visible to the team on GitHub.

---

## PHASE 8 — Summary

Print a final release summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  tdd-release: v{VERSION} shipped
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Merged branches ({count}):
   {list each}

❌ Failed branches ({count}):
   {list each — see .planning/release-log.md}

🚀 Release: https://github.com/squirrd/mc/releases/tag/v{VERSION}

Installed: mc {VERSION}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

If there were any failed branches, remind the user they can be picked up in the next release cycle once fixed.
