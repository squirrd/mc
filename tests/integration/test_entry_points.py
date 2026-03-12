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

    # --- Assert 2: update notification uses GitHub install URL ---
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
    assert "git+https://github.com/squirrd/mc" in output, (
        f"Update notification must reference GitHub install URL, got: {output!r}\n"
        "Expected: 'uv tool install --reinstall git+https://github.com/squirrd/mc'"
    )
