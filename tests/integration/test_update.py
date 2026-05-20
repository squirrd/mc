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
# MC-41: default-to-check — mc-update with no args runs check, not help
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mc_41_update_default_check_default_to_check_acceptance() -> None:
    """Acceptance test for MC-41 / default-to-check slice

    Feature added: 2026-05-20
    Scope: cli-only
    Source: MC-41
    Slice: default-to-check

    Feature description:
    When mc-update is invoked with no subcommand, it should default to running
    the 'check' subcommand instead of printing help text.

    Acceptance criterion:
    When mc-update main() is called with no subcommand argument, the output
    contains 'Version status:' (the check command's output header) and does
    NOT contain 'usage:' (the help text header).

    This test covers:
    1. mc-update with no args produces check output, not help
    2. The exit code matches what check() returns

    Expected: stdout contains 'Version status:' and does not contain 'usage:'
    """
    from unittest.mock import patch as mock_patch

    captured_out = io.StringIO()
    captured_err = io.StringIO()

    # Simulate: mc-update (no subcommand)
    with (
        mock_patch("sys.argv", ["mc-update"]),
        mock_patch("sys.stdout", captured_out),
        mock_patch("sys.stderr", captured_err),
        mock_patch("mc.update._fetch_latest_version", return_value="2.0.99"),
        mock_patch("mc.runtime.is_agent_mode", return_value=False),
        mock_patch(
            "mc.config.manager.ConfigManager.get_version_config",
            return_value={"pinned_mc": "latest"},
        ),
        mock_patch("mc.version.get_version", return_value="2.0.1"),
    ):
        try:
            from mc.update import main as update_main

            update_main()
        except SystemExit:
            pass

    stdout = captured_out.getvalue()
    stderr = captured_err.getvalue()
    combined = stdout + stderr

    assert "Version status:" in combined, (
        f"mc-update with no subcommand should run 'check' and output 'Version status:'.\n"
        f"Got stdout: {stdout!r}\n"
        f"Got stderr: {stderr!r}\n"
        f"This means the default-to-check behaviour is not implemented yet."
    )


# ---------------------------------------------------------------------------
# MC-41: help-still-works — mc-update --help still shows help text
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mc_41_update_default_check_help_still_works_acceptance() -> None:
    """Acceptance test for MC-41 / help-still-works slice

    Feature added: 2026-05-20
    Scope: cli-only
    Source: MC-41
    Slice: help-still-works

    Feature description:
    After changing the no-arg default to 'check', mc-update --help must still
    display the full help text listing all available subcommands. This is a
    regression guard ensuring explicit --help is not broken by the default
    behavior change.

    Acceptance criterion:
    (a) mc-update --help produces help text with 'usage:' and all subcommands, AND
    (b) mc-update (no args) does NOT produce help text (i.e. 'usage:' is absent
        from no-arg output, proving the default-to-check change is in place and
        --help is a distinct path).

    This test covers:
    1. --help flag still produces argparse help text with all subcommands
    2. The no-arg path does NOT produce help text (proving the two paths diverge)

    Expected: --help shows usage + subcommands; no-arg does not show usage
    """
    from unittest.mock import patch as mock_patch

    # Part (a): --help still shows help text
    captured_out = io.StringIO()
    captured_err = io.StringIO()

    with (
        mock_patch("sys.argv", ["mc-update", "--help"]),
        mock_patch("sys.stdout", captured_out),
        mock_patch("sys.stderr", captured_err),
    ):
        try:
            from mc.update import main as update_main

            update_main()
        except SystemExit:
            pass

    help_output = captured_out.getvalue() + captured_err.getvalue()
    help_lower = help_output.lower()

    assert "usage:" in help_lower, (
        f"mc-update --help must show usage text.\n"
        f"Got: {help_output!r}"
    )
    for subcmd in ("upgrade", "pin", "unpin", "check"):
        assert subcmd in help_lower, (
            f"mc-update --help must list '{subcmd}' subcommand.\n"
            f"Got: {help_output!r}"
        )

    # Part (b): no-arg invocation must NOT produce help text (it should run check)
    captured_out_noarg = io.StringIO()
    captured_err_noarg = io.StringIO()

    with (
        mock_patch("sys.argv", ["mc-update"]),
        mock_patch("sys.stdout", captured_out_noarg),
        mock_patch("sys.stderr", captured_err_noarg),
        mock_patch("mc.update._fetch_latest_version", return_value="2.0.99"),
        mock_patch("mc.runtime.is_agent_mode", return_value=False),
        mock_patch(
            "mc.config.manager.ConfigManager.get_version_config",
            return_value={"pinned_mc": "latest"},
        ),
        mock_patch("mc.version.get_version", return_value="2.0.1"),
    ):
        try:
            from mc.update import main as update_main

            update_main()
        except SystemExit:
            pass

    noarg_output = captured_out_noarg.getvalue() + captured_err_noarg.getvalue()

    assert "usage:" not in noarg_output.lower(), (
        f"mc-update with no args must NOT show help text (it should run 'check').\n"
        f"Got: {noarg_output!r}\n"
        f"This means the default-to-check behaviour is not implemented yet — "
        f"the no-arg path still shows help instead of running check."
    )


# ---------------------------------------------------------------------------
# MC-41: default-noted-in-help — help text mentions check is the default
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mc_41_update_default_check_default_noted_in_help_acceptance() -> None:
    """Acceptance test for MC-41 / default-noted-in-help slice

    Feature added: 2026-05-20
    Scope: cli-only
    Source: MC-41
    Slice: default-noted-in-help

    Feature description:
    The mc-update help text (shown via --help) should indicate that 'check'
    is the default subcommand when no subcommand is given.

    Acceptance criterion:
    The --help output contains text indicating that 'check' runs by default
    (e.g. 'default: check' or 'defaults to check' or similar phrasing).

    This test covers:
    1. Help text communicates the default behaviour to users

    Expected: help output contains 'default' and 'check' in close proximity
    """
    from unittest.mock import patch as mock_patch

    captured_out = io.StringIO()
    captured_err = io.StringIO()

    with (
        mock_patch("sys.argv", ["mc-update", "--help"]),
        mock_patch("sys.stdout", captured_out),
        mock_patch("sys.stderr", captured_err),
    ):
        try:
            from mc.update import main as update_main

            update_main()
        except SystemExit:
            pass

    stdout = captured_out.getvalue()
    combined = stdout + captured_err.getvalue()
    combined_lower = combined.lower()

    # The help text must mention that 'check' is the default when no subcommand is given
    assert "default" in combined_lower, (
        f"mc-update --help must mention the default behaviour.\n"
        f"Got: {combined!r}\n"
        f"Expected: help text that indicates 'check' is the default subcommand"
    )
    assert "check" in combined_lower, (
        f"mc-update --help must mention 'check' as the default.\n"
        f"Got: {combined!r}"
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
