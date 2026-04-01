"""Regression test for worktree-venv-isolation

Bug discovered: 2026-04-01
Platform: macOS / Both
Severity: major
Source: ad-hoc

Problem:
create-worktree.sh runs `uv pip install -e ".[dev]"` from the worktree directory
without first creating a local .venv. When no VIRTUAL_ENV is active, uv pip
discovers the main repo's .venv by walking up the directory tree and installs the
editable package into it, overwriting __editable__.mc-*.pth to point at the new
worktree's src/ instead of the main repo's src/. This means:
1. The main repo's .venv editable install is corrupted — imports resolve to the
   wrong source tree.
2. The worktree has no isolated .venv of its own, so it shares the main repo's
   venv entirely, making independent per-worktree testing impossible.

Steps to reproduce:
1. Ensure main repo .venv exists with editable install pointing at main/src.
2. Run: bash .claude/commands/tdd-issue/scripts/create-worktree.sh fix/_temp-test
3. Read main .venv __editable__.mc-*.pth — it now points at the worktree's src/.

Expected: After create-worktree.sh completes, the main repo's .venv editable
          .pth still points at the main repo's src/ directory, AND the new
          worktree has its own isolated .venv with a .pth pointing at the
          worktree's src/.
Actual:   The main repo's .venv editable .pth is overwritten with the new
          worktree's src/ path; the worktree has no .venv of its own.

This test ensures the bug does not regress.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

# This file lives at: <worktree>/tests/integration/test_worktree_isolation.py
# Three .parent calls reach the worktree root.
_WORKTREE_ROOT = Path(__file__).parent.parent.parent

# The main repo root is derived via git so this test works when run from any worktree.
# git rev-parse --git-common-dir returns the shared .git dir (e.g. /path/to/main/.git)
_git_common_dir = subprocess.run(
    ["git", "rev-parse", "--git-common-dir"],
    cwd=str(_WORKTREE_ROOT),
    capture_output=True,
    text=True,
    check=True,
).stdout.strip()
_MAIN_REPO = Path(_git_common_dir).parent  # .git → repo root

_MAIN_VENV = _MAIN_REPO / ".venv"
# Use the script from the current worktree so the test exercises the version under
# development. When run from the main branch, _WORKTREE_ROOT == _MAIN_REPO, so this
# continues to test the canonical script after merging.
_CREATE_WORKTREE_SCRIPT = _WORKTREE_ROOT / ".claude/commands/tdd-issue/scripts/create-worktree.sh"
_TEMP_BRANCH = "fix/_temp-worktree-isolation-regression"
_TEMP_WORKTREE = _MAIN_REPO / ".tdd/worktrees/fix/_temp-worktree-isolation-regression"


def _main_pth_content() -> str:
    """Return current content of the main .venv editable .pth file."""
    pth_files = list(_MAIN_VENV.glob("lib/python*/site-packages/__editable__.mc-*.pth"))
    assert pth_files, f"No editable .pth found in main .venv: {_MAIN_VENV}"
    return pth_files[0].read_text().strip()


def _cleanup() -> None:
    """Remove temp worktree and branch, then restore main .venv editable install."""
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(_TEMP_WORKTREE)],
        cwd=str(_MAIN_REPO),
        capture_output=True,
    )
    subprocess.run(
        ["git", "branch", "-D", _TEMP_BRANCH],
        cwd=str(_MAIN_REPO),
        capture_output=True,
    )
    # Restore main .venv editable install to point at main repo src/
    subprocess.run(
        ["uv", "pip", "install", "-e", ".[dev]", "--quiet"],
        cwd=str(_MAIN_REPO),
        capture_output=True,
    )


@pytest.mark.integration
def test_worktree_venv_isolation_regression() -> None:
    """Regression: create-worktree.sh must not corrupt the main repo's editable .pth.

    After create-worktree.sh runs:
    - The main repo's .venv __editable__.mc-*.pth MUST still point at main/src.
    - The new worktree MUST have its own isolated .venv.
    - The worktree's own .venv .pth MUST point at the worktree's src/.
    """
    # Guard: script must exist
    assert _CREATE_WORKTREE_SCRIPT.exists(), (
        f"create-worktree.sh not found at {_CREATE_WORKTREE_SCRIPT}"
    )

    # Baseline: confirm main .venv .pth starts pointing at main repo src/
    original_pth = _main_pth_content()
    expected_main_src = str(_MAIN_REPO / "src")
    assert expected_main_src in original_pth, (
        f"Baseline failed: main .venv .pth does not contain main src/\n"
        f"  actual: {original_pth}\n"
        f"  expected substring: {expected_main_src}"
    )

    try:
        # Run create-worktree.sh without VIRTUAL_ENV set — simulates a fresh shell,
        # which is exactly the scenario that triggers the bug.
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        result = subprocess.run(
            ["bash", str(_CREATE_WORKTREE_SCRIPT), _TEMP_BRANCH],
            cwd=str(_MAIN_REPO),
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"create-worktree.sh failed with exit {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # Assertion 1: main .venv .pth must STILL point at main repo src/
        pth_after = _main_pth_content()
        assert expected_main_src in pth_after, (
            f"BUG REGRESSED: create-worktree.sh corrupted main .venv editable install\n"
            f"  .pth before: {original_pth}\n"
            f"  .pth after:  {pth_after}\n"
            f"  The worktree's src path is now in the main .venv .pth.\n"
            f"  Any `uv run` from the main repo will import from the wrong source."
        )

        # Assertion 2: the worktree must have its own isolated .venv
        worktree_venv = _TEMP_WORKTREE / ".venv"
        assert worktree_venv.exists(), (
            f"BUG REGRESSED: new worktree has no isolated .venv at {worktree_venv}\n"
            f"  Without its own .venv, the worktree shares the main repo's .venv,\n"
            f"  causing cross-worktree source contamination."
        )

        # Assertion 3: the worktree's own .venv .pth must point at the worktree's src/
        worktree_pth_files = list(
            worktree_venv.glob("lib/python*/site-packages/__editable__.mc-*.pth")
        )
        assert worktree_pth_files, (
            f"BUG REGRESSED: worktree .venv has no editable .pth at "
            f"{worktree_venv}/lib/python*/site-packages/__editable__.mc-*.pth"
        )
        worktree_pth = worktree_pth_files[0].read_text().strip()
        expected_worktree_src = str(_TEMP_WORKTREE / "src")
        assert expected_worktree_src in worktree_pth, (
            f"BUG REGRESSED: worktree .venv .pth does not point at worktree src/\n"
            f"  .pth content: {worktree_pth}\n"
            f"  expected:     {expected_worktree_src}"
        )

    finally:
        _cleanup()
