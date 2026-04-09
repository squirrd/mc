#!/usr/bin/env bash
# bootstrap.sh — Initialise .tdd/ directory structure for tdd-issue skill
# Idempotent: safe to run on every skill invocation

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
TDD_DIR="$REPO_ROOT/.tdd"
ISSUES_DIR="$TDD_DIR/issues"
WORKTREES_DIR="$TDD_DIR/worktrees"
TRACKING_FILE="$ISSUES_DIR/ISSUE_TRACKING.md"
TEMPLATE_FILE="$REPO_ROOT/.claude/commands/tdd-issue/assets/tracking-template.md"
GITIGNORE="$REPO_ROOT/.gitignore"

# Create directories
mkdir -p "$ISSUES_DIR"
mkdir -p "$WORKTREES_DIR"

# Seed tracking file from template if it does not exist
if [[ ! -f "$TRACKING_FILE" ]]; then
    if [[ -f "$TEMPLATE_FILE" ]]; then
        cp "$TEMPLATE_FILE" "$TRACKING_FILE"
    else
        # Fallback minimal seed
        cat > "$TRACKING_FILE" <<'EOF'
# Issue Tracking

Last updated: (not yet updated)

---

## Active Issues

(none)

---

## Completed Issues

(none)
EOF
    fi
    echo "Created $TRACKING_FILE"
fi

# Add .tdd/ to .gitignore if not already present
if [[ -f "$GITIGNORE" ]]; then
    if ! grep -qxF '.tdd/' "$GITIGNORE"; then
        printf '\n# TDD worktrees and issue tracking (local only)\n.tdd/\n' >> "$GITIGNORE"
        echo "Added .tdd/ to .gitignore"
    fi
else
    printf '# TDD worktrees and issue tracking (local only)\n.tdd/\n' > "$GITIGNORE"
    echo "Created .gitignore with .tdd/ entry"
fi

echo "Bootstrap complete: $TDD_DIR"
