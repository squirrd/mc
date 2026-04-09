"""Integration tests for CLI entry points.

Tests verify the `mc` command is correctly registered and executable
when installed via uv tool install or uv run.
"""
import os
import subprocess
import sys

import pytest
from pytest_console_scripts import ScriptRunner


def test_mc_version(script_runner: ScriptRunner) -> None:
    """Test mc --version command returns version info."""
    result = script_runner.run(['mc', '--version'])
    assert result.returncode == 0
    assert 'mc' in result.stdout
    # Version number must be present in semver format (e.g. 2.0.4, not a hardcoded literal)
    import re
    assert re.search(r'\d+\.\d+\.\d+', result.stdout), (
        f"Expected semver in stdout, got: {result.stdout!r}"
    )


def test_mc_help(script_runner: ScriptRunner) -> None:
    """Test mc --help command displays help text."""
    result = script_runner.run(['mc', '--help'])
    assert result.returncode == 0
    assert 'usage:' in result.stdout.lower() or 'MC CLI' in result.stdout


def test_mc_invalid_command(script_runner: ScriptRunner) -> None:
    """Test mc handles invalid commands gracefully."""
    result = script_runner.run(['mc', 'nonexistent-command'])
    # Should exit with error code, not crash
    assert result.returncode != 0


@pytest.mark.integration
def test_remove_legacy_env_check_regression() -> None:
    """Regression test for ad-hoc 2026-03-08 — legacy env var check removed.

    Bug discovered: 2026-03-08
    Platform: Both
    Severity: major
    Source: ad-hoc

    Problem:
    check_legacy_env_vars() in cli/main.py hard-errors and calls sys.exit(1)
    whenever RH_API_OFFLINE_TOKEN or MC_BASE_DIR is present in the environment.
    Many users have these vars set from the v1.x era and cannot use the CLI
    until they manually unset them, even though the CLI no longer reads them.

    Steps to reproduce:
    1. Export RH_API_OFFLINE_TOKEN=anything in the shell
    2. Run any mc subcommand (e.g. mc version)
    3. Observe the CLI exits immediately with the legacy env var error

    Expected: CLI runs normally regardless of whether legacy env vars are set in
              the environment — they are simply ignored.
    Actual:   CLI aborts with exit code 1 and prints "Legacy environment variables
              detected" before executing any command.

    This test ensures the bug does not regress.
    """
    env = os.environ.copy()
    env["RH_API_OFFLINE_TOKEN"] = "some_legacy_token"

    # Use `mc ldap --help` — a subcommand that passes argument parsing without
    # requiring external services. (mc version was removed as a subcommand.)
    result = subprocess.run(
        [sys.executable, "-m", "mc.cli.main", "ldap", "--help"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert "Legacy environment variables detected" not in result.stdout, (
        f"Legacy env var check is still present — it should have been removed.\n"
        f"stdout: {result.stdout}"
    )
    # Should not abort due to the env var check
    assert result.returncode != 1 or "Legacy environment variables" not in result.stdout, (
        f"mc version exited {result.returncode} with RH_API_OFFLINE_TOKEN set.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


@pytest.mark.integration
def test_rename_package_to_mc_regression() -> None:
    """Regression test for ad-hoc 2026-03-12 — package renamed from mc-cli to mc.

    Bug discovered: 2026-03-12
    Platform: Both
    Severity: minor
    Source: ad-hoc

    Problem:
    The package was named "mc-cli" in pyproject.toml despite the project being
    GitHub-only (not published to PyPI). This caused two concrete bugs:

    1. The update notification told users to run:
         uvx --reinstall mc-cli@latest
       which only works for PyPI packages. Since mc is GitHub-only, this command
       fails silently — users cannot update via the displayed instruction.

    2. `uv tool install git+https://github.com/squirrd/mc` registered the tool
       as "mc-cli", making `uv tool upgrade mc` (in update.py) target the wrong
       tool name. Only `uv tool upgrade mc-cli` would work, but no code or
       documentation said so.

    Root cause:
    pyproject.toml `name = "mc-cli"` creates a mismatch between the uv tool
    registration name and the command name ("mc"). For a GitHub-only project
    there is no reason to use a disambiguating suffix.

    Expected behaviour:
    - Package metadata name is "mc"
    - Update notification instructs: uv tool install --reinstall git+https://github.com/squirrd/mc
    - uv tool upgrade mc (in update.py) targets the correct tool name

    Actual behaviour (before fix):
    - Package metadata name is "mc-cli"
    - Update notification instructs: uvx --reinstall mc-cli@latest (PyPI-only, broken)
    """
    from importlib.metadata import PackageNotFoundError, metadata
    from io import StringIO
    from unittest.mock import MagicMock, patch

    from mc.version_check import VersionChecker

    # --- Assert 1: package metadata name ---
    try:
        meta = metadata("mc")
        assert meta["Name"] == "mc", (
            f"Package metadata Name is '{meta['Name']}', expected 'mc'. "
            "pyproject.toml name must be changed from 'mc-cli' to 'mc'."
        )
    except PackageNotFoundError:
        pytest.fail(
            "Package 'mc' not found via importlib.metadata. "
            "pyproject.toml name must be changed from 'mc-cli' to 'mc' "
            "and the package reinstalled."
        )

    # --- Assert 2: update notification directs user to mc-update upgrade ---
    checker = VersionChecker()
    mock_cfg = MagicMock()
    mock_cfg.get.return_value = None
    mock_cfg.load.return_value = {"version": {}}
    mock_cfg.save_atomic.return_value = None
    checker._config_manager = mock_cfg

    captured = StringIO()
    with patch("sys.stderr", captured):
        checker._display_notification("2.0.4", "2.0.5")

    output = captured.getvalue()
    assert "mc-update upgrade" in output, (
        f"Update notification must direct user to 'mc-update upgrade', got: {output!r}\n"
        "Expected: 'mc v2.0.5 available. Run: mc-update upgrade'"
    )


@pytest.mark.integration
def test_remove_update_feature_regression() -> None:
    """Regression test for MC-5 — mc version subcommand must be removed.

    Bug discovered: 2026-04-09
    Platform: Both
    Severity: minor
    Source: MC-5

    Problem:
    The CLI registers a 'version' (alias: 'ver') subcommand with an '--update' flag
    that duplicates functionality already available via 'mc --version'. This creates
    two ways to check the version, with the subcommand additionally triggering a
    manual update check. The subcommand should be removed entirely; 'mc --version'
    is the only supported way to display the version string.

    Steps to reproduce:
    1. Run: mc version
    2. Observe: exits 0 and prints "mc version <N.N.N>"
    3. Run: mc version --update
    4. Observe: exits 0 and triggers a manual version check
    5. Run: mc --help
    6. Observe: 'version (ver)' appears in the subcommand list

    Expected:
    - 'mc version' exits with a non-zero code (unknown subcommand)
    - 'mc --version' still works and prints a semver string (e.g. "mc 2.0.18")
    - 'mc --help' does not list 'version' or 'ver' in the subcommand list

    Actual (before fix):
    - 'mc version' exits 0 and prints "mc version 2.0.18"
    - 'mc version --update' exits 0 and checks for updates
    - 'mc --help' lists 'version (ver)' as a valid subcommand

    This test ensures the bug does not regress.
    """
    import re

    # --- Assert 1: 'mc version' must NOT be a valid subcommand ---
    result_version = subprocess.run(
        [sys.executable, "-m", "mc.cli.main", "version"],
        capture_output=True,
        text=True,
    )
    assert result_version.returncode != 0, (
        f"'mc version' should not be a valid subcommand (expected non-zero exit), "
        f"but exited {result_version.returncode}.\n"
        f"stdout: {result_version.stdout!r}\n"
        f"stderr: {result_version.stderr!r}\n"
        "The 'version' subcommand must be removed from cli/main.py."
    )

    # --- Assert 2: 'mc --version' must still work and print a semver string ---
    result_flag = subprocess.run(
        [sys.executable, "-m", "mc.cli.main", "--version"],
        capture_output=True,
        text=True,
    )
    assert result_flag.returncode == 0, (
        f"'mc --version' must still work, but exited {result_flag.returncode}.\n"
        f"stdout: {result_flag.stdout!r}\n"
        f"stderr: {result_flag.stderr!r}"
    )
    combined = result_flag.stdout + result_flag.stderr
    assert re.search(r"\d+\.\d+\.\d+", combined), (
        f"'mc --version' must print a semver version string, got: {combined!r}"
    )

    # --- Assert 3: 'mc --help' must not list 'version' as a subcommand ---
    result_help = subprocess.run(
        [sys.executable, "-m", "mc.cli.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result_help.returncode == 0, (
        f"'mc --help' must exit 0, but exited {result_help.returncode}."
    )
    # The subcommand list is on the line starting with the positional args block.
    # Match the pattern where 'version' or 'ver' appears as a subcommand token.
    subcommand_line = ""
    for line in result_help.stdout.splitlines():
        if "{" in line and "}" in line and "attachments" in line:
            subcommand_line = line
            break
    assert "version" not in subcommand_line and "ver" not in subcommand_line, (
        f"'mc --help' still lists 'version'/'ver' in the subcommand list.\n"
        f"Subcommand line: {subcommand_line!r}\n"
        "The 'version' subparser registration must be removed from cli/main.py."
    )
