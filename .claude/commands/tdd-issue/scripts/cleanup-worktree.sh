#!/usr/bin/env bash
# cleanup-worktree.sh — Remove a worktree, optionally merge branch into target, delete branch
#
# Usage:
#   cleanup-worktree.sh <branch-path>
#   cleanup-worktree.sh <branch-path> --merge-into <target-branch>
#
# Examples:
#   cleanup-worktree.sh fix/container-attach-leak --merge-into main
#   cleanup-worktree.sh fix/container-attach-leak/test-fd-cleanup --merge-into fix/container-attach-leak
#
# Safety:
#   - Aborts on merge conflict — does NOT force
#   - Aborts if branch does not exist
#   - Aborts if worktree has uncommitted changes

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <branch-path> [--merge-into <target>]" >&2
    exit 1
fi

BRANCH_PATH="$1"
MERGE_INTO=""

# Parse optional --merge-into flag
shift
while [[ $# -gt 0 ]]; do
    case "$1" in
        --merge-into)
            MERGE_INTO="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_PATH="$REPO_ROOT/.tdd/worktrees/$BRANCH_PATH"

# Verify branch exists
if ! git show-ref --verify --quiet "refs/heads/$BRANCH_PATH"; then
    echo "ERROR: Branch '$BRANCH_PATH' does not exist." >&2
    exit 1
fi

# Remove worktree if it exists
if git worktree list --porcelain | grep -q "worktree $WORKTREE_PATH$"; then
    # Check for uncommitted changes in the worktree
    if [[ -d "$WORKTREE_PATH" ]]; then
        DIRTY=$(git -C "$WORKTREE_PATH" status --porcelain 2>/dev/null | head -1)
        if [[ -n "$DIRTY" ]]; then
            echo "ERROR: Worktree at $WORKTREE_PATH has uncommitted changes." >&2
            echo "Commit or stash changes before running cleanup." >&2
            exit 1
        fi
    fi
    git worktree remove "$WORKTREE_PATH"
    echo "Removed worktree: $WORKTREE_PATH"
else
    git worktree prune 2>/dev/null || true
    echo "Note: Worktree not found at $WORKTREE_PATH (may already be removed)"
fi

# Merge into target branch (if requested)
if [[ -n "$MERGE_INTO" ]]; then
    echo "Merging '$BRANCH_PATH' into '$MERGE_INTO'..."

    # Detect if MERGE_INTO is currently checked out in another worktree.
    # git won't let you `git checkout` a branch that is live in a worktree,
    # so we detect this and run the merge from inside that worktree instead.
    MERGE_INTO_WORKTREE=""
    current_wt=""
    while IFS= read -r line; do
        if [[ "$line" =~ ^worktree[[:space:]](.+)$ ]]; then
            current_wt="${BASH_REMATCH[1]}"
        elif [[ "$line" == "branch refs/heads/$MERGE_INTO" ]]; then
            MERGE_INTO_WORKTREE="$current_wt"
            break
        fi
    done < <(git worktree list --porcelain)

    if [[ -n "$MERGE_INTO_WORKTREE" ]]; then
        # Target branch is live in a worktree — run merge from there
        echo "Note: '$MERGE_INTO' is checked out in worktree at $MERGE_INTO_WORKTREE"
        echo "Running merge from within that worktree..."
        if ! git -C "$MERGE_INTO_WORKTREE" merge --no-ff "$BRANCH_PATH" -m "Merge branch '$BRANCH_PATH' into $MERGE_INTO"; then
            echo "" >&2
            echo "ERROR: Merge conflict detected. Aborting." >&2
            echo "Resolve conflicts manually in: $MERGE_INTO_WORKTREE" >&2
            echo "Then run:" >&2
            echo "  git -C $MERGE_INTO_WORKTREE merge --continue" >&2
            echo "  git branch -d $BRANCH_PATH" >&2
            git -C "$MERGE_INTO_WORKTREE" merge --abort 2>/dev/null || true
            exit 1
        fi
        MERGE_SHA="$(git -C "$MERGE_INTO_WORKTREE" rev-parse --short HEAD)"
    else
        # Target branch is not in a worktree — checkout and merge normally
        CURRENT_BRANCH="$(git branch --show-current)"
        git checkout "$MERGE_INTO"

        # Attempt no-ff merge — abort on conflict
        if ! git merge --no-ff "$BRANCH_PATH" -m "Merge branch '$BRANCH_PATH' into $MERGE_INTO"; then
            echo "" >&2
            echo "ERROR: Merge conflict detected. Aborting." >&2
            echo "Resolve conflicts manually, then run:" >&2
            echo "  git merge --continue" >&2
            echo "  git branch -d $BRANCH_PATH" >&2
            git merge --abort 2>/dev/null || true
            git checkout "$CURRENT_BRANCH" 2>/dev/null || true
            exit 1
        fi
        MERGE_SHA="$(git rev-parse --short HEAD)"
    fi

    echo "Merged '$BRANCH_PATH' → '$MERGE_INTO' (sha: $MERGE_SHA)"
fi

# Delete the branch
git branch -d "$BRANCH_PATH"
echo "Deleted branch: $BRANCH_PATH"

if [[ -n "$MERGE_INTO" ]]; then
    echo ""
    echo "Cleanup complete:"
    echo "  Merged : $BRANCH_PATH → $MERGE_INTO"
    echo "  SHA    : $MERGE_SHA"
else
    echo "Cleanup complete: $BRANCH_PATH"
fi
