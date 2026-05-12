"""Integration tests for CLI entry points.

Tests verify the `mc` command is correctly registered and executable
when installed via uv tool install or uv run.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from pytest_console_scripts import ScriptRunner

from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


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


@pytest.mark.integration
def test_hide_quick_access_help_regression() -> None:
    """Regression test for MC-51 — quick_access must not appear in mc --help output.

    Bug discovered: 2026-05-11
    Platform: Both
    Severity: minor
    Source: MC-51

    Problem:
    The quick_access subcommand is registered with argparse.SUPPRESS as its help
    text, but argparse.SUPPRESS only hides the help description — it does NOT
    remove the subcommand name from the choices list or the subcommand summary.
    As a result, 'quick_access' appears in the help output alongside the literal
    text '==SUPPRESS==', which is confusing and exposes an internal implementation
    detail to users.

    Steps to reproduce:
    1. Run: mc --help
    2. Observe: 'quick_access' appears in the subcommand choices list
    3. Observe: 'quick_access        ==SUPPRESS==' appears in the help body

    Expected:
    - 'quick_access' does NOT appear anywhere in mc --help output
    - '==SUPPRESS==' does NOT appear anywhere in mc --help output
    - The help text mentions that 'mc <case_number>' is valid shorthand
      for quick case access

    Actual (before fix):
    - 'quick_access' appears in the choices list: {attachments,...,quick_access,...}
    - The help body shows: 'quick_access        ==SUPPRESS=='
    - There is no mention of the 'mc <case_number>' shorthand in --help

    This test ensures the bug does not regress.
    """
    result = subprocess.run(
        [sys.executable, "-m", "mc.cli.main", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"mc --help should exit 0, got {result.returncode}.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )

    help_output = result.stdout

    # --- Assert 1: 'quick_access' must not appear anywhere in help output ---
    assert "quick_access" not in help_output, (
        f"'quick_access' is visible in --help output. "
        f"It should be completely hidden from the user.\n"
        f"stdout:\n{help_output}"
    )

    # --- Assert 2: '==SUPPRESS==' must not leak into help output ---
    assert "SUPPRESS" not in help_output, (
        f"'==SUPPRESS==' text is leaking into --help output. "
        f"argparse internals should never be visible to users.\n"
        f"stdout:\n{help_output}"
    )

    # --- Assert 3: help should mention the mc <case_number> shorthand ---
    # The quick_access feature allows `mc 12345678` as shorthand for
    # `mc case 12345678`. Since the subcommand is hidden, the help text
    # should document this shorthand so users can discover it.
    help_lower = help_output.lower()
    has_shorthand_hint = (
        "case_number" in help_lower
        or "case number" in help_lower
        or "<case" in help_lower
        or "mc <8" in help_lower
        or "8-digit" in help_lower
        or "shorthand" in help_lower
    )
    assert has_shorthand_hint, (
        f"mc --help does not mention the 'mc <case_number>' shorthand. "
        f"Since quick_access is hidden, the help text should document "
        f"this feature so users can discover it.\n"
        f"stdout:\n{help_output}"
    )


def _podman_available() -> bool:
    """Check if Podman is available for integration tests."""
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False


def _image_exists() -> bool:
    """Check if the mc container image is available."""
    try:
        client = PodmanClient()
        client.client.images.get("mc-rhel10:latest")
        return True
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
@pytest.mark.skipif(not _image_exists(), reason="mc-rhel10:latest image not found")
def test_agent_base_dir_check_regression() -> None:
    """Regression test for MC-57 — agent commands must not fail on host base_dir validation.

    Bug discovered: 2026-05-11
    Platform: Both
    Severity: major
    Source: MC-57

    Problem:
    main() in cli/main.py unconditionally validates that base_dir (read from the
    host-mounted config file) exists on the filesystem before routing to any command.
    Inside a container, base_dir is a host path (e.g. /Users/dsquirre/mc) that does
    not exist. Agent commands (mc agent init-case, mc agent backplane-login) never use
    base_dir — they use WORKSPACE_PATH=/case — but the validation kills the process
    with exit 1 before the agent command routing is reached.

    Steps to reproduce:
    1. Create a container with mc container create (host config is mounted read-only)
    2. Inside the container, run: mc agent init-case
    3. Observe: exit 1 with "The directory '/Users/dsquirre/mc' must exist"

    Expected: mc agent init-case proceeds past base_dir validation and executes
              the agent init-case logic (may fail for other reasons like missing
              CASE_NUMBER env var, but NOT because of base_dir).
    Actual:   mc agent init-case exits 1 with base_dir validation error before
              the agent command is even reached.

    This test ensures the bug does not regress.
    """
    client = PodmanClient()
    state_db = StateDatabase(":memory:")
    manager = ContainerManager(client, state_db)

    container_name = "mc-99922233"
    try:
        # Clean up any leftover container from a previous run
        subprocess.run(
            ["podman", "rm", "-f", container_name],
            capture_output=True,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            container = manager.create(
                case_number="99922233",
                workspace_path=tmpdir,
                customer_name="AgentBaseDirCheck",
            )

            result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "mc", "agent", "init-case",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            combined_output = result.stdout + result.stderr

            assert "must exist" not in combined_output, (
                f"mc agent init-case hit the base_dir validation inside the container.\n"
                f"exit code: {result.returncode}\n"
                f"stdout: {result.stdout!r}\n"
                f"stderr: {result.stderr!r}\n"
                f"\nBug: cli/main.py line 167-169 unconditionally validates base_dir "
                f"(read from host-mounted config) before reaching agent command routing. "
                f"The host path does not exist in the container.\n"
                f"Fix: skip base_dir validation when get_runtime_mode() == 'agent'."
            )

    finally:
        subprocess.run(
            ["podman", "rm", "-f", container_name],
            capture_output=True,
        )


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_agent_init_case_path_regression() -> None:
    """Regression test for MC-61 — published container image must include MC-57 fix.

    Bug discovered: 2026-05-12
    Platform: Both
    Severity: major
    Source: MC-61

    Problem:
    The code fix for MC-57 (commit 61fba39) correctly skips base_dir validation
    when running in agent mode. However, the published container image at
    quay.io/rhn_support_dsquirre/mc-container:latest was not rebuilt after the
    fix was merged. As a result, any container created from the published image
    still has the old code that unconditionally validates base_dir from the
    host-mounted config file. Running `mc agent init-case` inside the container
    fails with exit 1 and "The directory '/Users/<user>/mc' must exist" because
    the host path does not exist in the container filesystem.

    Steps to reproduce:
    1. Create a container via `mc container create` (pulls from quay.io)
    2. Inside the container, run: mc agent init-case
    3. Observe: exit 1 with "The directory '/Users/dsquirre/mc' must exist"

    Expected: mc agent init-case inside a container created from the published
              quay.io image proceeds past base_dir validation. It may fail for
              other reasons (e.g. missing CASE_NUMBER env var), but NOT because
              of host base_dir validation.
    Actual:   mc agent init-case exits 1 with base_dir validation error before
              the agent command is even reached, because the published image
              does not include the MC-57 fix.

    This test ensures the published container image is kept in sync with the
    source code. Unlike test_agent_base_dir_check_regression (MC-57) which
    validates the local image, this test validates the image pulled from
    quay.io by ContainerManager.create().

    This test ensures the bug does not regress.
    """
    client = PodmanClient()
    state_db = StateDatabase(":memory:")
    manager = ContainerManager(client, state_db)

    container_name = "mc-99933344"
    try:
        # Clean up any leftover container from a previous run
        subprocess.run(
            ["podman", "rm", "-f", container_name],
            capture_output=True,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a container using the standard flow — this pulls from
            # quay.io/rhn_support_dsquirre/mc-container:latest (the published image).
            # Unlike test_agent_base_dir_check_regression which uses the local
            # mc-rhel10:latest image, this validates the actual published artifact.
            container = manager.create(
                case_number="99933344",
                workspace_path=tmpdir,
                customer_name="AgentInitCasePath",
            )

            # Run mc agent init-case WITHOUT injecting any source fixes.
            # If the published image still has the old code (pre MC-57 fix),
            # this will exit 1 with "The directory '/Users/<user>/mc' must exist".
            result = subprocess.run(
                [
                    "podman", "exec", container_name,
                    "mc", "agent", "init-case",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            combined_output = result.stdout + result.stderr

            # The bug manifests as "must exist" in the output — the host
            # base_dir path fails validation inside the container.
            assert "must exist" not in combined_output, (
                f"mc agent init-case hit the base_dir validation inside the "
                f"published container image (quay.io). The image needs to be "
                f"rebuilt with the MC-57 fix (commit 61fba39).\n"
                f"exit code: {result.returncode}\n"
                f"stdout: {result.stdout!r}\n"
                f"stderr: {result.stderr!r}\n"
                f"\nThe published image at quay.io/rhn_support_dsquirre/"
                f"mc-container:latest is stale and must be rebuilt from "
                f"current main which includes the base_dir validation skip "
                f"for agent mode."
            )

    finally:
        subprocess.run(
            ["podman", "rm", "-f", container_name],
            capture_output=True,
        )
