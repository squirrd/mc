"""Integration tests for mc-update user-facing message hygiene.

Bug: MC-9
Discovered: 2026-04-14
Platform: macOS / Linux (host mode only)
Severity: minor

Problem:
mc-update exposes raw ``uv`` CLI commands in user-facing error and recovery
messages.  Users should only ever see ``mc-update`` commands — never internal
``uv`` plumbing.

Affected messages (before fix):
  - _print_recovery_instructions():
      "Upgrade failed. To recover, run:\\n  uv tool install --force git+..."
  - _verify_mc_version() on FileNotFoundError:
      "Error: mc not found on PATH after upgrade. Check: uv tool list"
  - _run_upgrade() on FileNotFoundError:
      "Error: uv not found. Install from https://docs.astral.sh/uv/"
  - pin() on FileNotFoundError:
      "Error: uv not found. Install from https://docs.astral.sh/uv/"
  - pin() on install failure:
      "To retry: uv tool install --force git+...@v{version}"

Expected: all user-facing stderr/stdout must reference ``mc-update``
commands only, never raw ``uv`` invocations.

These tests are RED until the source is fixed.
"""

from __future__ import annotations

import io
import sys
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# _print_recovery_instructions
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_recovery_instructions_no_uv_commands() -> None:
    """_print_recovery_instructions() must not expose uv commands to users.

    Bug: Before the fix the function prints:
        "Upgrade failed. To recover, run:\\n  uv tool install --force git+..."

    Expected after fix: output references mc-update, not uv.

    This test is RED until the source is fixed.
    """
    from mc.update import _print_recovery_instructions

    captured_err = io.StringIO()
    with patch("sys.stderr", captured_err):
        _print_recovery_instructions()

    output = captured_err.getvalue()

    assert "uv " not in output, (
        f"_print_recovery_instructions() must not expose uv commands to users.\n"
        f"Got: {output!r}\n"
        f"Expected: only mc-update commands (e.g. 'mc-update upgrade')"
    )
    assert "mc-update" in output, (
        f"_print_recovery_instructions() must direct users to mc-update.\n"
        f"Got: {output!r}"
    )


# ---------------------------------------------------------------------------
# _verify_mc_version
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_verify_mc_version_not_found_no_uv_commands() -> None:
    """_verify_mc_version() FileNotFoundError must not mention uv tool list.

    Bug: Before the fix the function prints:
        "Error: mc not found on PATH after upgrade. Check: uv tool list"

    This test is RED until the source is fixed.
    """
    from mc.update import _verify_mc_version

    captured_err = io.StringIO()
    with patch("sys.stderr", captured_err), patch("subprocess.run", side_effect=FileNotFoundError):
        _verify_mc_version()

    output = captured_err.getvalue()

    assert "uv " not in output, (
        f"_verify_mc_version() must not expose uv commands to users.\n"
        f"Got: {output!r}"
    )


# ---------------------------------------------------------------------------
# _run_upgrade
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_run_upgrade_not_found_no_uv_commands() -> None:
    """_run_upgrade() FileNotFoundError must not mention uv install instructions.

    Bug: Before the fix the function prints:
        "Error: uv not found. Install from https://docs.astral.sh/uv/"

    This test is RED until the source is fixed.
    """
    from mc.update import _run_upgrade

    captured_err = io.StringIO()
    with patch("sys.stderr", captured_err), patch("subprocess.run", side_effect=FileNotFoundError):
        _run_upgrade()

    output = captured_err.getvalue()

    assert "uv " not in output, (
        f"_run_upgrade() must not expose uv commands to users.\n"
        f"Got: {output!r}"
    )


# ---------------------------------------------------------------------------
# pin — FileNotFoundError path
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pin_not_found_no_uv_commands() -> None:
    """pin() FileNotFoundError must not mention uv not found.

    Bug: Before the fix the function prints:
        "Error: uv not found. Install from https://docs.astral.sh/uv/"

    This test is RED until the source is fixed.
    """
    from mc.update import pin

    mock_cfg_instance = MagicMock()
    mock_cfg_instance.update_version_config.return_value = None

    captured_err = io.StringIO()
    with (
        patch("sys.stderr", captured_err),
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("mc.update._validate_version_exists", return_value=True),
        patch("mc.config.manager.ConfigManager", return_value=mock_cfg_instance),
        patch("subprocess.run", side_effect=FileNotFoundError),
    ):
        pin("2.0.3")

    output = captured_err.getvalue()

    assert "uv " not in output, (
        f"pin() must not expose uv commands to users on FileNotFoundError.\n"
        f"Got: {output!r}"
    )


# ---------------------------------------------------------------------------
# pin — install failure path
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_pin_install_failure_no_uv_commands() -> None:
    """pin() install failure must not mention uv tool install --force.

    Bug: Before the fix the function prints:
        "To retry: uv tool install --force git+...@v{version}"

    This test is RED until the source is fixed.
    """
    from mc.update import pin

    mock_result = MagicMock()
    mock_result.returncode = 1

    mock_cfg_instance = MagicMock()
    mock_cfg_instance.update_version_config.return_value = None

    captured_err = io.StringIO()
    with (
        patch("sys.stderr", captured_err),
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("mc.update._validate_version_exists", return_value=True),
        patch("mc.config.manager.ConfigManager", return_value=mock_cfg_instance),
        patch("subprocess.run", return_value=mock_result),
    ):
        pin("2.0.3")

    output = captured_err.getvalue()

    assert "uv " not in output, (
        f"pin() must not expose uv commands to users on install failure.\n"
        f"Got: {output!r}"
    )


# ---------------------------------------------------------------------------
# Regression: source-level scan for uv commands in user-facing messages
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mc_update_no_uv_cmds_regression() -> None:
    """Regression test for mc-update-no-uv-cmds: no raw uv commands in user messages.

    Bug discovered: 2026-04-20
    Platform: Both
    Severity: minor
    Source: ad-hoc

    Problem:
    update.py exposed raw ``uv`` CLI commands (e.g. ``uv tool install --force``,
    ``uv not found``, ``uv tool list``) in user-facing error and recovery messages
    printed to stderr/stdout via ``print()``. Users should only see ``mc-update``
    commands, never internal ``uv`` plumbing.

    Steps to reproduce:
    1. Call _run_upgrade() when uv is not on PATH -> prints "uv not found"
    2. Call _print_recovery_instructions() -> prints "uv tool install --force ..."
    3. Call _verify_mc_version() when mc is not on PATH -> prints "uv tool list"
    4. Call pin() when uv install fails -> prints "uv tool install --force ..."

    Expected: all user-facing print() calls reference mc-update commands only
    Actual:   (before fix) print() calls contain raw "uv tool install", "uv not found",
              "uv tool list" strings

    This test ensures the bug does not regress.
    """
    import ast
    import inspect
    import textwrap

    import mc.update as update_module

    source = inspect.getsource(update_module)
    tree = ast.parse(source)

    # Patterns that must NOT appear in user-facing string literals inside print() calls.
    # These are the exact uv command fragments that were in the old messages.
    banned_fragments = [
        "uv tool install",
        "uv tool upgrade",
        "uv tool list",
        "uv not found",
    ]

    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # Match print(...) calls
        func = node.func
        is_print = (isinstance(func, ast.Name) and func.id == "print") or (
            isinstance(func, ast.Attribute) and func.attr == "print"
        )
        if not is_print:
            continue

        # Extract all string constants from the print() arguments
        for arg in node.args:
            for child in ast.walk(arg):
                if isinstance(child, ast.Constant) and isinstance(child.value, str):
                    for fragment in banned_fragments:
                        if fragment in child.value:
                            violations.append(
                                f"Line ~{child.lineno}: print() contains "
                                f"banned fragment {fragment!r} in: {child.value!r}"
                            )

    assert not violations, (
        "update.py must not expose raw uv commands in user-facing print() calls.\n"
        "Violations found:\n" + textwrap.indent("\n".join(violations), "  ")
    )
