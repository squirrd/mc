#!/usr/bin/env bash
# create-worktree.sh — Create a git branch + worktree for tdd-issue
#
# Usage:
#   create-worktree.sh fix/<shortFixName>
#   create-worktree.sh fix/<shortFixName>--<unitTestName>
#
# Behaviour:
#   - Top-level branch (fix/<name>): branches from main
#   - Unit-test branch (fix/<name>--<unit>): branches from fix/<name>
#     Branch name uses -- separator; worktree path uses / separator.
#     e.g. branch fix/container-attach-leak--test-fd-cleanup
#          worktree .tdd/worktrees/fix/container-attach-leak/test-fd-cleanup
#   - Idempotent: if worktree already exists, prints warning and exits 0

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 <branch-path>" >&2
    echo "  Examples:" >&2
    echo "    $0 fix/container-attach-leak" >&2
    echo "    $0 fix/container-attach-leak--test-fd-cleanup" >&2
    exit 1
fi

BRANCH_PATH="$1"
REPO_ROOT="$(git rev-parse --show-toplevel)"

# Convert branch name to worktree path:
# fix/<name>--<unit> → .tdd/worktrees/fix/<name>/<unit>
# fix/<name>         → .tdd/worktrees/fix/<name>
WORKTREE_RELATIVE="${BRANCH_PATH//--//}"
WORKTREE_PATH="$REPO_ROOT/.tdd/worktrees/$WORKTREE_RELATIVE"

# Derive parent branch:
# - fix/<name>          → parent is main (no -- separator)
# - fix/<name>--<unit>  → parent is fix/<name> (split on first --)
if [[ "$BRANCH_PATH" == *"--"* ]]; then
    PARENT_BRANCH="${BRANCH_PATH%%--*}"
else
    PARENT_BRANCH="main"
fi

# Guard: idempotent if worktree already exists
if git worktree list --porcelain | grep -q "worktree $WORKTREE_PATH$"; then
    echo "WARNING: Worktree already exists at $WORKTREE_PATH — skipping creation." >&2
    exit 0
fi

# Guard: prune stale worktree registrations first
git worktree prune 2>/dev/null || true

# Ensure the parent branch exists (for unit-test worktrees)
if [[ "$PARENT_BRANCH" != "main" ]]; then
    if ! git show-ref --verify --quiet "refs/heads/$PARENT_BRANCH"; then
        echo "ERROR: Parent branch '$PARENT_BRANCH' does not exist." >&2
        echo "Create the issue worktree first before creating unit test worktrees." >&2
        exit 1
    fi
fi

# Create the branch if it does not already exist
if git show-ref --verify --quiet "refs/heads/$BRANCH_PATH"; then
    echo "Branch '$BRANCH_PATH' already exists — attaching worktree to existing branch."
    git worktree add "$WORKTREE_PATH" "$BRANCH_PATH"
else
    echo "Creating branch '$BRANCH_PATH' from '$PARENT_BRANCH'..."
    git worktree add -b "$BRANCH_PATH" "$WORKTREE_PATH" "$PARENT_BRANCH"
fi

echo "Worktree created:"
echo "  Branch  : $BRANCH_PATH"
echo "  Path    : $WORKTREE_PATH"
echo "  Parent  : $PARENT_BRANCH"

# Pre-seed the virtual environment with all dev dependencies so agents don't
# hit ModuleNotFoundError when collecting tests with optional extras.
if command -v uv &>/dev/null && [[ -f "$WORKTREE_PATH/pyproject.toml" ]]; then
    echo "Syncing dev dependencies in worktree..."
    (cd "$WORKTREE_PATH" && uv pip install -e ".[dev]" --quiet) \
        && echo "  venv    : dev dependencies installed" \
        || echo "WARNING: uv pip install -e '[dev]' failed — run manually if tests fail to collect." >&2
fi
