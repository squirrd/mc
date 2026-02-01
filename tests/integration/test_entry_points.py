"""Integration tests for CLI entry points.

Tests verify the `mc` command is correctly registered and executable
when installed via uv tool install or uv run.
"""
from pytest_console_scripts import ScriptRunner


def test_mc_version(script_runner: ScriptRunner) -> None:
    """Test mc --version command returns version info."""
    result = script_runner.run(['mc', '--version'])
    assert result.returncode == 0
    assert 'mc' in result.stdout
    assert '2.0.0' in result.stdout


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
