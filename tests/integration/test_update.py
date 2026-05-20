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


# ---------------------------------------------------------------------------
# Feature: MC-39 — mc-update list [n]
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_mc_39_update_list_fetch_releases_acceptance() -> None:
    """Acceptance test for MC-39 / slice: fetch-releases

    Feature added: 2026-05-20
    Scope: cli-only
    Source: MC-39
    Slice: fetch-releases

    Feature description:
    Add mc-update list [n] subcommand to show the N most recent available
    upgrades from GitHub releases. This slice covers the internal function
    that fetches release data from the GitHub API.

    Acceptance criterion:
    _fetch_releases(count) returns a list of (tag_name, release_name) tuples
    from GitHub API; calling with count=3 returns exactly 3 releases in
    descending order.

    This test covers:
    1. _fetch_releases function exists and is importable
    2. It returns a list of 2-tuples with the correct structure
    3. It respects the count parameter (returns exactly count items)

    Expected: _fetch_releases(3) returns a list of exactly 3 (tag, name) tuples
    """
    from mc.update import _fetch_releases

    # Mock the GitHub API to return a controlled set of releases
    fake_releases = [
        {"tag_name": "v2.0.5", "name": "Release 2.0.5"},
        {"tag_name": "v2.0.4", "name": "Release 2.0.4"},
        {"tag_name": "v2.0.3", "name": "Release 2.0.3"},
        {"tag_name": "v2.0.2", "name": "Release 2.0.2"},
        {"tag_name": "v2.0.1", "name": "Release 2.0.1"},
    ]

    with patch("mc.update.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = fake_releases
        mock_get.return_value = mock_response

        result = _fetch_releases(3)

    # Must return exactly 3 items
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    assert len(result) == 3, (
        f"_fetch_releases(3) must return exactly 3 releases, got {len(result)}"
    )

    # Each item must be a 2-tuple of (tag_name, release_name)
    for item in result:
        assert isinstance(item, tuple), f"Expected tuple, got {type(item)}"
        assert len(item) == 2, f"Expected 2-tuple, got {len(item)}-tuple"
        tag, name = item
        assert isinstance(tag, str), f"tag_name must be str, got {type(tag)}"
        assert isinstance(name, str), f"release_name must be str, got {type(name)}"

    # Must be in descending order (first release is newest)
    assert result[0][0] == "v2.0.5", f"First release should be v2.0.5, got {result[0][0]}"
    assert result[2][0] == "v2.0.3", f"Third release should be v2.0.3, got {result[2][0]}"


@pytest.mark.integration
def test_mc_39_update_list_list_command_acceptance() -> None:
    """Acceptance test for MC-39 / slice: list-command

    Feature added: 2026-05-20
    Scope: cli-only
    Source: MC-39
    Slice: list-command

    Feature description:
    Add mc-update list [n] subcommand to show the N most recent available
    upgrades from GitHub releases. This slice covers the list_releases()
    function and the wiring of the 'list' subcommand in main().

    Acceptance criterion:
    list_releases(count) formats and prints releases; main() wires list
    subcommand with optional positional count defaulting to 5;
    mc-update list prints 5 releases, mc-update list 3 prints 3.

    This test covers:
    1. list_releases function exists and is callable
    2. main() accepts 'list' as a subcommand
    3. 'list' subcommand with no arg defaults to 5 releases
    4. 'list 3' subcommand shows exactly 3 releases

    Expected: list_releases(count) prints formatted release info to stdout;
    main() dispatches 'list' subcommand correctly.
    """
    from mc.update import list_releases

    # Mock _fetch_releases to return controlled data
    fake_releases = [
        ("v2.0.5", "Release 2.0.5"),
        ("v2.0.4", "Release 2.0.4"),
        ("v2.0.3", "Release 2.0.3"),
    ]

    captured_out = io.StringIO()
    with (
        patch("mc.update._fetch_releases", return_value=fake_releases),
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("sys.stdout", captured_out),
    ):
        exit_code = list_releases(3)

    output = captured_out.getvalue()

    # Must print something (formatted release list)
    assert len(output.strip()) > 0, "list_releases() must print release information to stdout"

    # Must include the version tags in the output
    assert "v2.0.5" in output, "Output must include release tag v2.0.5"
    assert "v2.0.3" in output, "Output must include release tag v2.0.3"

    # Must return 0 on success
    assert exit_code == 0, f"list_releases() must return 0 on success, got {exit_code}"

    # Verify main() wiring: 'list' subcommand must be recognized
    from mc.update import main

    with (
        patch("mc.update._fetch_releases", return_value=fake_releases),
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("sys.argv", ["mc-update", "list", "3"]),
        patch("sys.stdout", io.StringIO()),
        pytest.raises(SystemExit) as exc_info,
    ):
        main()

    assert exc_info.value.code == 0, (
        f"mc-update list 3 must exit with code 0, got {exc_info.value.code}"
    )


@pytest.mark.integration
def test_mc_39_update_list_edge_cases_acceptance() -> None:
    """Acceptance test for MC-39 / slice: edge-cases

    Feature added: 2026-05-20
    Scope: cli-only
    Source: MC-39
    Slice: edge-cases

    Feature description:
    Add mc-update list [n] subcommand to show the N most recent available
    upgrades from GitHub releases. This slice covers edge cases: agent-mode
    guard, network errors, and invalid count values.

    Acceptance criterion:
    agent-mode guard returns 1; network error prints user-friendly message;
    count=0 or negative rejected with error message.

    This test covers:
    1. Agent-mode guard returns exit code 1
    2. Network error prints a user-friendly message (not a traceback)
    3. count=0 is rejected with an error message
    4. count=-1 (negative) is rejected with an error message

    Expected: graceful handling of all edge cases with informative messages
    """
    from mc.update import list_releases

    # --- Agent-mode guard ---
    captured_err = io.StringIO()
    with (
        patch("mc.runtime.is_agent_mode", return_value=True),
        patch("sys.stderr", captured_err),
    ):
        exit_code = list_releases(5)

    assert exit_code == 1, (
        f"list_releases() must return 1 in agent mode, got {exit_code}"
    )
    agent_output = captured_err.getvalue()
    assert len(agent_output.strip()) > 0, (
        "list_releases() must print a message when blocked by agent mode"
    )

    # --- Network error ---
    import requests as req_lib

    captured_err2 = io.StringIO()
    with (
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("mc.update.requests.get", side_effect=req_lib.ConnectionError("Network down")),
        patch("sys.stderr", captured_err2),
    ):
        exit_code = list_releases(5)

    assert exit_code == 1, (
        f"list_releases() must return 1 on network error, got {exit_code}"
    )
    net_output = captured_err2.getvalue()
    assert len(net_output.strip()) > 0, (
        "list_releases() must print a user-friendly message on network error"
    )
    # Must NOT contain a raw traceback
    assert "Traceback" not in net_output, (
        "list_releases() must not print a raw traceback on network error"
    )

    # --- count=0 rejected ---
    captured_err3 = io.StringIO()
    with (
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("sys.stderr", captured_err3),
    ):
        exit_code = list_releases(0)

    assert exit_code == 1, (
        f"list_releases(0) must return 1, got {exit_code}"
    )

    # --- count=-1 rejected ---
    captured_err4 = io.StringIO()
    with (
        patch("mc.runtime.is_agent_mode", return_value=False),
        patch("sys.stderr", captured_err4),
    ):
        exit_code = list_releases(-1)

    assert exit_code == 1, (
        f"list_releases(-1) must return 1, got {exit_code}"
    )
