#!/bin/bash
# Run full test suite (unit + integration).
# Exit 0 = all pass, non-zero = failures.
#
# Usage:
#   bash scripts/release/run_tests.sh
#   bash scripts/release/run_tests.sh --unit-only

set -euo pipefail

if [[ "${1:-}" == "--unit-only" ]]; then
    echo "▶ Running unit tests..."
    uv run pytest tests/unit/ -q --tb=short
else
    echo "▶ Running full test suite (unit + integration)..."
    uv run pytest tests/unit/ tests/integration/ -q --tb=short
fi
