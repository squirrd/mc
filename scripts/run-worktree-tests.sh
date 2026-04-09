#!/usr/bin/env bash
# run-worktree-tests.sh — Run pytest inside a TDD worktree
#
# Usage:
#   run-worktree-tests.sh <branch> [--log-dir <path>] [<pytest-args>...]
#
# Examples:
#   run-worktree-tests.sh fix/my-bug
#   run-worktree-tests.sh fix/my-bug --log-dir .tdd/issues/my-bug tests/unit/test_foo.py
#   run-worktree-tests.sh fix/my-bug--unit-test-name tests/integration/test_bar.py
#
# Branch → worktree path uses the same -- → / convention as create-worktree.sh:
#   fix/my-bug                → .tdd/worktrees/fix/my-bug
#   fix/my-bug--unit-test     → .tdd/worktrees/fix/my-bug/unit-test
#
# Output:
#   Full output is saved to <log-dir>/test-<timestamp>.log
#   A context-friendly summary (FAILED/ERROR/E /AssertionError/summary lines) is printed to stdout.
#   The log file path is announced so callers can Read it for full details.

set -euo pipefail

if [[ $# -lt 1 ]]; then
    echo "Usage: $0 <branch> [--log-dir <path>] [<pytest-args>...]" >&2
    echo "  Examples:" >&2
    echo "    $0 fix/my-bug" >&2
    echo "    $0 fix/my-bug --log-dir .tdd/issues/my-bug tests/unit/test_foo.py" >&2
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

# Parse optional --log-dir argument
LOG_DIR="/tmp"
if [[ "${1:-}" == "--log-dir" ]]; then
    LOG_DIR="$2"
    shift 2
    mkdir -p "$LOG_DIR"
fi

SRC_PATH="$WORKTREE_PATH/src"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG_FILE="$LOG_DIR/test-${TIMESTAMP}.log"

echo "Worktree : $WORKTREE_PATH"
echo "PYTHONPATH: $SRC_PATH"
echo "Args     : $*"
echo "Log      : $LOG_FILE"
echo "---"

# Run pytest with -q --tb=short defaults; save full output to log file
# Use the worktree's own .venv if present to prevent cross-worktree contamination.
# Without this, uv run walks up the directory tree and may pick up the main repo's .venv.
cd "$WORKTREE_PATH"
WORKTREE_VENV_ARGS=()
if [[ -d "$WORKTREE_PATH/.venv" ]]; then
    WORKTREE_VENV_ARGS=(env VIRTUAL_ENV="$WORKTREE_PATH/.venv")
fi
PYTHONPATH="$SRC_PATH" "${WORKTREE_VENV_ARGS[@]}" uv run pytest -q --tb=short -p no:cov --override-ini="addopts=" "$@" 2>&1 | tee "$LOG_FILE"
EXIT_CODE=${PIPESTATUS[0]}

# Print intelligent context summary
echo ""
echo "--- Context summary (full output: $LOG_FILE) ---"
grep -E "^(FAILED|ERROR|E |AssertionError|=====)" "$LOG_FILE" | head -25 || true

exit $EXIT_CODE
