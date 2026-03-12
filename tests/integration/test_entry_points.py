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

    # Use `mc version` — a subcommand that passes argument parsing and reaches
    # the check_legacy_env_vars() call site (unlike --help which exits earlier).
    result = subprocess.run(
        [sys.executable, "-m", "mc.cli.main", "version"],
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
