#!/usr/bin/env bash
# run-worktree-tests.sh — Run pytest inside a TDD worktree
#
# Usage:
#   run-worktree-tests.sh <branch> [<pytest-args>...]
#
# Examples:
#   run-worktree-tests.sh fix/my-bug
#   run-worktree-tests.sh fix/my-bug tests/unit/test_foo.py -v -s
#   run-worktree-tests.sh fix/my-bug--unit-test-name tests/integration/test_bar.py -v
#
# Branch → worktree path uses the same -- → / convention as create-worktree.sh:
#   fix/my-bug                → .tdd/worktrees/fix/my-bug
#   fix/my-bug--unit-test     → .tdd/worktrees/fix/my-bug/unit-test

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <branch> [<pytest-args>...]" >&2
    echo "  Examples:" >&2
    echo "    $0 fix/my-bug" >&2
    echo "    $0 fix/my-bug tests/unit/test_foo.py -v -s" >&2
    exit 1
fi

BRANCH_PATH="$1"
shift

REPO_ROOT="$(git rev-parse --show-toplevel)"
WORKTREE_RELATIVE="${BRANCH_PATH//--//}"
WORKTREE_PATH="$REPO_ROOT/.tdd/worktrees/$WORKTREE_RELATIVE"

if [[ ! -d "$WORKTREE_PATH" ]]; then
    echo "ERROR: Worktree not found at $WORKTREE_PATH" >&2
    echo "Available worktrees:" >&2
    git worktree list --porcelain | grep "^worktree " | grep "\.tdd/worktrees" | sed 's|worktree ||' >&2
    exit 1
fi

SRC_PATH="$WORKTREE_PATH/src"

echo "Worktree : $WORKTREE_PATH"
echo "PYTHONPATH: $SRC_PATH"
echo "Args     : $*"
echo "---"

cd "$WORKTREE_PATH"
PYTHONPATH="$SRC_PATH" uv run pytest -p no:cov --override-ini="addopts=" "$@"
