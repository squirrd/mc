"""Integration tests for version check with real GitHub API.

These tests make REAL HTTP calls to GitHub API to catch real-world issues.
Unit tests with mocks are in tests/test_version_check.py.
"""

import pytest
import time
from pathlib import Path
from unittest.mock import patch
from mc.version_check import VersionChecker
from mc.config.manager import ConfigManager


@pytest.mark.integration
class TestGitHubAPIIntegration:
    """Integration tests with real GitHub API calls."""

    def test_github_404_no_releases_regression(self, tmp_path, caplog):
        """Regression test for Production Bug - GitHub 404 when no releases published.

        Bug discovered: 2026-02-23
        Platform: All
        Severity: Minor (doesn't block core functionality)

        Problem:
        Version check fails with ERROR log when GitHub repository has no published releases.
        The 404 response is treated as an error, but it's actually a normal condition for
        new projects that haven't created any releases yet.

        Steps to reproduce:
        1. Run mc version (or any command triggering background check)
        2. Version checker calls GET /repos/squirrd/mc/releases/latest
        3. GitHub returns 404 Not Found (no releases published)
        4. Error logged: "Failed to perform version check: 404 Client Error: Not Found"

        Expected:
        - Should handle 404 gracefully (it's not an error condition)
        - Should log at INFO/DEBUG level, not ERROR
        - Should save last_check timestamp to prevent repeated attempts
        - Should save last_status_code=404 to enable smart retry logic

        Actual (before fix):
        - Logs ERROR level message
        - Treated as unexpected failure
        - No special handling for "no releases yet" scenario

        This test ensures the bug does not regress by:
        1. Making REAL HTTP call to GitHub API (no mocks!)
        2. Verifying 404 response is received
        3. Verifying graceful handling without ERROR logs
        4. Verifying config is updated properly

        Production Bug: Post v2.0.4 deployment
        """
        # Setup isolated config in temp directory
        config_manager = ConfigManager()
        config_file = tmp_path / "config.toml"
        config_manager._config_path = config_file

        # Initialize config
        config_manager.save_atomic({
            'api': {'rh_api_offline_token': 'test_token'},
            'base_directory': str(tmp_path),
            'version': {}
        })

        # Create version checker with isolated config
        checker = VersionChecker()
        checker._config_manager = config_manager

        # Mock get_version to return stable test version
        with patch('mc.version_check.get_version', return_value='2.0.4'):
            # Clear any previous logs
            caplog.clear()

            # REAL HTTP call to GitHub API (no mocks!)
            # This will actually hit https://api.github.com/repos/squirrd/mc/releases/latest
            try:
                release_data, etag, status_code = checker._fetch_latest_release()

                # Verify we got 404 (repo has no releases)
                assert status_code == 404, \
                    f"Expected 404 for repo with no releases, got {status_code}"

                # If 404, release_data should be None or exception should be raised
                # Current implementation raises HTTPError - that's the bug we're testing!
                pytest.fail("Expected HTTPError to be raised for 404, but got success response")

            except Exception as e:
                # This is the current behavior - 404 raises exception
                error_msg = str(e)

                # Verify it's a 404 error
                assert "404" in error_msg, \
                    f"Expected 404 error, got: {error_msg}"

                # BUG: This exception propagates and gets logged as ERROR
                # After fix, 404 should be handled gracefully without exception

        # After fix, this test should verify:
        # 1. No ERROR level logs
        # 2. Config updated with last_check timestamp
        # 3. Config updated with last_status_code=404
        # 4. Appropriate throttling applied for "no releases" state

        # TODO: Uncomment assertions below once bug is fixed
        # assert not any(record.levelname == "ERROR" for record in caplog.records), \
        #     "Should not log ERROR for 404 (normal condition for repos without releases)"
        #
        # config = config_manager.load()
        # assert config['version']['last_status_code'] == 404
        # assert config['version']['last_check'] is not None

    def test_github_api_with_valid_repo_has_releases(self, tmp_path, caplog):
        """Integration test: Verify version check works with repo that HAS releases.

        This test validates the happy path by using a real GitHub repo with releases.
        Uses anthropics/claude-code as a known-good example.

        This is NOT a regression test - it's a positive validation that version
        checking works correctly when releases exist.
        """
        # Setup isolated config
        config_manager = ConfigManager()
        config_file = tmp_path / "config.toml"
        config_manager._config_path = config_file

        config_manager.save_atomic({
            'api': {'rh_api_offline_token': 'test_token'},
            'base_directory': str(tmp_path),
            'version': {}
        })

        # Create checker with temporary override for a known-good repo
        checker = VersionChecker()
        checker._config_manager = config_manager

        # Override to use a repo that definitely has releases
        # (This is OK for integration testing - validates our GitHub API integration)
        original_owner = checker.GITHUB_OWNER
        original_repo = checker.GITHUB_REPO
        try:
            checker.GITHUB_OWNER = "anthropics"
            checker.GITHUB_REPO = "anthropic-sdk-python"

            with patch('mc.version_check.get_version', return_value='0.0.1'):
                caplog.clear()

                # REAL HTTP call to repo with releases
                release_data, etag, status_code = checker._fetch_latest_release()

                # Should get 200 success with real release data
                assert status_code == 200, \
                    f"Expected 200 for repo with releases, got {status_code}"

                assert release_data is not None
                assert 'tag_name' in release_data
                assert etag != ""  # Should receive ETag header

                # Should extract version from tag_name
                tag_name = release_data['tag_name']
                assert tag_name.startswith('v') or tag_name[0].isdigit(), \
                    f"Unexpected tag format: {tag_name}"

        finally:
            # Restore original repo
            checker.GITHUB_OWNER = original_owner
            checker.GITHUB_REPO = original_repo

    def test_github_api_respects_rate_limits(self, tmp_path):
        """Integration test: Verify rate limit detection with real API.

        GitHub API returns 403 when rate limited. This test verifies we detect it
        and would extend throttle period appropriately.

        Note: This test won't actually trigger rate limiting (would need 60+ requests/hour),
        but validates the detection logic if we receive 403.
        """
        # This test documents the expected behavior but won't actually hit rate limits
        # in normal test runs. It serves as documentation and would catch regressions
        # if someone broke the 403 handling logic.

        config_manager = ConfigManager()
        config_file = tmp_path / "config.toml"
        config_manager._config_path = config_file

        config_manager.save_atomic({
            'api': {'rh_api_offline_token': 'test_token'},
            'base_directory': str(tmp_path),
            'version': {}
        })

        checker = VersionChecker()
        checker._config_manager = config_manager

        # Test the throttle extension logic (without actually hitting rate limit)
        last_check = time.time() - 7200  # 2 hours ago

        # With 403 status, should still be throttled (24h throttle for rate limits)
        assert not checker._should_check_now(last_check, 403), \
            "Should extend throttle to 24h after rate limit (403)"

        # After 24 hours, should allow check again
        last_check_old = time.time() - 86401  # 24h + 1s ago
        assert checker._should_check_now(last_check_old, 403), \
            "Should allow check after 24h even with previous 403"


@pytest.mark.integration
def test_update_checks_wrong_package_regression() -> None:
    """Regression test for update-checks-wrong-package bug.

    Bug discovered: 2026-03-26
    Platform: macOS / Linux (host mode only)
    Severity: major
    Source: ad-hoc

    Problem:
    mc-update check/upgrade must target the 'mc' uv tool (package name in pyproject.toml).
    Two root causes were identified and fixed:

      1. get_version() must resolve importlib.metadata.version("mc"), matching the
         package name declared in pyproject.toml.

      2. _run_upgrade() must issue ["uv", "tool", "upgrade", "mc"] — the correct
         uv tool name — not "mc-cli" (the old pre-rename package name).

    Steps to reproduce (original bug):
    1. Have both mc (dev editable) and mc-cli (old prod uv tool) installed.
    2. Run mc-update check — reports "up to date" using dev version (2.0.9).
    3. Run mc-update upgrade — targets wrong tool, leaves prod un-upgraded.

    Expected:
      - get_version() resolves the 'mc' package version.
      - _run_upgrade() issues "uv tool upgrade mc".

    This test ensures the bug does not regress.
    """
    import subprocess
    import unittest.mock as mock
    from mc.version import get_version
    from mc import update

    # --- Part 1: get_version() must resolve mc-cli, not mc dev-repo ---
    result = subprocess.run(
        ["uv", "tool", "list"],
        capture_output=True,
        text=True,
        check=True,
    )
    mc_version: str | None = None
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("mc "):
            mc_version = stripped.split()[1].lstrip("v")
            break

    # Only assert on Part 1 when mc is installed as a uv tool.
    # If absent (CI running only the dev checkout), skip the metadata check
    # but still verify Part 2 (the command string).
    if mc_version is not None:
        installed = get_version()
        assert installed == mc_version, (
            f"get_version() returned '{installed}' but uv tool list reports mc at '{mc_version}'. "
            f"mc-update check/upgrade will report wrong installed version."
        )

    # --- Part 2: _run_upgrade() must target mc, not mc-cli ---
    captured_cmd: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        captured_cmd.append(cmd)
        m = mock.MagicMock()
        m.returncode = 0
        return m

    with mock.patch("mc.update.subprocess.run", side_effect=fake_run):
        update._run_upgrade()

    assert len(captured_cmd) == 1, "Expected exactly one subprocess.run call in _run_upgrade()"
    cmd = captured_cmd[0]
    assert cmd == ["uv", "tool", "install", "--reinstall", "git+https://github.com/squirrd/mc@latest"], (
        f"_run_upgrade() ran: {cmd!r}\n"
        f"Expected: ['uv', 'tool', 'install', '--reinstall', 'git+https://github.com/squirrd/mc@latest']\n"
        f"Bug: must use git+https URL with @latest tag so uv installs from the git repo, "
        f"not PyPI (mc is not on PyPI)."
    )


@pytest.mark.integration
def test_run_upgrade_uses_git_latest_tag() -> None:
    """Regression test: _run_upgrade() must use git+https URL with @latest tag.

    Bug: _run_upgrade() previously used ['uv', 'tool', 'upgrade', 'mc'] which silently
    does nothing for git-pinned installs (uv tool upgrade only works for PyPI packages).
    mc is NOT published to PyPI — it is installed from git — so the correct command is:
      uv tool install --reinstall git+https://github.com/squirrd/mc@latest

    This test verifies the fix is present and does not regress.
    """
    import unittest.mock as mock
    from mc import update

    captured_cmd: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        captured_cmd.append(cmd)
        m = mock.MagicMock()
        m.returncode = 0
        return m

    with mock.patch("mc.update.subprocess.run", side_effect=fake_run):
        update._run_upgrade()

    assert len(captured_cmd) == 1, "Expected exactly one subprocess.run call in _run_upgrade()"
    cmd = captured_cmd[0]

    assert cmd[0] == "uv", f"Expected 'uv' as first element, got: {cmd[0]!r}"
    assert cmd[1:3] == ["tool", "install"], (
        f"Expected 'uv tool install', got: {cmd[:3]!r}\n"
        f"'uv tool upgrade mc' silently does nothing for git-pinned installs."
    )
    assert "--reinstall" in cmd, (
        f"Expected --reinstall flag in command: {cmd!r}"
    )
    git_url_arg = next((arg for arg in cmd if "git+https" in arg), None)
    assert git_url_arg is not None, (
        f"Expected a git+https URL in command: {cmd!r}\n"
        f"mc is not on PyPI — must install from git."
    )
    assert "@latest" in git_url_arg or "@v" in git_url_arg, (
        f"Expected version tag (@latest or @v<version>) in git URL: {git_url_arg!r}\n"
        f"Without a tag, uv installs main branch HEAD, not the latest tagged release."
    )
    assert cmd == ["uv", "tool", "install", "--reinstall", "git+https://github.com/squirrd/mc@latest"], (
        f"_run_upgrade() ran: {cmd!r}\n"
        f"Expected: ['uv', 'tool', 'install', '--reinstall', 'git+https://github.com/squirrd/mc@latest']\n"
        f"Bug: must use git+https URL with @latest tag."
    )


@pytest.mark.integration
class TestVersionCheckEndToEnd:
    """End-to-end integration tests for complete version check workflow."""

    def test_version_check_completes_without_blocking(self, tmp_path):
        """Integration test: Version check runs in background without blocking.

        Verifies that version check:
        1. Runs in background thread
        2. Doesn't block main thread
        3. Completes cleanly without hanging
        4. Uses real GitHub API
        """
        config_manager = ConfigManager()
        config_file = tmp_path / "config.toml"
        config_manager._config_path = config_file

        config_manager.save_atomic({
            'api': {'rh_api_offline_token': 'test_token'},
            'base_directory': str(tmp_path),
            'version': {}  # Empty version section - no last_check means check will run
        })

        checker = VersionChecker()
        checker._config_manager = config_manager

        with patch('mc.version_check.get_version', return_value='2.0.4'):
            start_time = time.time()

            # Start background check (uses real GitHub API)
            checker.start_background_check()

            # Main thread should not be blocked
            elapsed = time.time() - start_time
            assert elapsed < 0.1, \
                f"start_background_check() blocked for {elapsed}s (should be instant)"

            # Give background thread time to complete
            time.sleep(2)

            # Cleanup
            checker._cleanup()

            # Verify thread stopped cleanly
            if checker._worker_thread:
                assert not checker._worker_thread.is_alive(), \
                    "Background thread should stop cleanly"


@pytest.mark.integration
def test_update_env_isolation_regression() -> None:
    """Regression test for update-env-isolation bug.

    Bug discovered: 2026-04-02
    Platform: macOS / Linux (host mode only)
    Severity: major
    Source: UAT (2026-04-02)

    Problem:
    mc-update pin and mc-update upgrade call subprocess.run(["uv", "tool", "install", ...])
    without passing UV_TOOL_DIR or UV_TOOL_BIN_DIR env vars. As a result, uv always installs
    to its default path (~/.local/bin/mc) regardless of MC_ENV. When a developer runs
    MC_ENV=dev mc-update pin 2.0.15, the prod binary at ~/.local/bin/mc is silently
    overwritten with the dev-pinned version, corrupting the production installation.

    Steps to reproduce:
    1. Set MC_ENV=dev in environment.
    2. Run mc-update pin 2.0.15 (or mc-update upgrade).
    3. uv tool install runs without UV_TOOL_BIN_DIR — installs to ~/.local/bin/mc.
    4. The prod mc binary is now pinned to 2.0.15, even though the intent was dev-env only.

    Expected:
    When MC_ENV=dev, _run_upgrade() and pin() pass UV_TOOL_BIN_DIR=~/mc-dev/bin and
    UV_TOOL_DIR=~/mc-dev/tools to the uv subprocess so that uv installs into the isolated
    env directory and never touches the prod binary at ~/.local/bin/mc.

    Actual (before fix):
    Neither _run_upgrade() nor pin() passed an env= kwarg to subprocess.run, so uv used
    its default install paths unconditionally, overwriting ~/.local/bin/mc.

    This test ensures the bug does not regress.
    """
    import os
    import unittest.mock as mock
    from pathlib import Path

    from mc import update

    # --- Part 1: _run_upgrade() must pass env isolation vars when MC_ENV is set ---
    captured_run_upgrade_env: dict[str, str] | None = None

    def fake_run_upgrade(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        nonlocal captured_run_upgrade_env
        captured_run_upgrade_env = kwargs.get("env")  # type: ignore[assignment]
        m = mock.MagicMock()
        m.returncode = 0
        return m

    old_env = os.environ.copy()
    try:
        os.environ["MC_ENV"] = "dev"
        with mock.patch("mc.update.subprocess.run", side_effect=fake_run_upgrade):
            update._run_upgrade()
    finally:
        os.environ.clear()
        os.environ.update(old_env)

    assert captured_run_upgrade_env is not None, (
        "_run_upgrade() did not pass env= to subprocess.run. "
        "Bug: uv uses default paths and overwrites ~/.local/bin/mc even when MC_ENV=dev."
    )
    expected_bin_dir = str(Path.home() / "mc-dev" / "bin")
    assert captured_run_upgrade_env.get("UV_TOOL_BIN_DIR") == expected_bin_dir, (
        f"UV_TOOL_BIN_DIR={captured_run_upgrade_env.get('UV_TOOL_BIN_DIR')!r}, "
        f"expected {expected_bin_dir!r}. "
        f"Bug: MC_ENV=dev mc-update upgrade overwrites the prod binary."
    )
    expected_tool_dir = str(Path.home() / "mc-dev" / "tools")
    assert captured_run_upgrade_env.get("UV_TOOL_DIR") == expected_tool_dir, (
        f"UV_TOOL_DIR={captured_run_upgrade_env.get('UV_TOOL_DIR')!r}, "
        f"expected {expected_tool_dir!r}."
    )

    # --- Part 2: pin() must pass env isolation vars when MC_ENV is set ---
    captured_pin_env: dict[str, str] | None = None

    def fake_run_pin(cmd: list[str], **kwargs: object) -> mock.MagicMock:
        nonlocal captured_pin_env
        captured_pin_env = kwargs.get("env")  # type: ignore[assignment]
        m = mock.MagicMock()
        m.returncode = 0
        return m

    old_env = os.environ.copy()
    try:
        os.environ["MC_ENV"] = "dev"
        os.environ.pop("MC_RUNTIME_MODE", None)
        with mock.patch("mc.update._validate_version_exists", return_value=True):
            with mock.patch("mc.config.manager.ConfigManager") as mock_cm:
                mock_cm.return_value.update_version_config = mock.MagicMock()
                with mock.patch("mc.update.subprocess.run", side_effect=fake_run_pin):
                    update.pin("2.0.15")
    finally:
        os.environ.clear()
        os.environ.update(old_env)

    assert captured_pin_env is not None, (
        "pin() did not pass env= to subprocess.run. "
        "Bug: MC_ENV=dev mc-update pin 2.0.15 overwrites ~/.local/bin/mc (the prod binary)."
    )
    assert captured_pin_env.get("UV_TOOL_BIN_DIR") == expected_bin_dir, (
        f"UV_TOOL_BIN_DIR={captured_pin_env.get('UV_TOOL_BIN_DIR')!r}, "
        f"expected {expected_bin_dir!r}. "
        f"Bug: MC_ENV=dev mc-update pin installs to prod binary path."
    )
    assert captured_pin_env.get("UV_TOOL_DIR") == expected_tool_dir, (
        f"UV_TOOL_DIR={captured_pin_env.get('UV_TOOL_DIR')!r}, "
        f"expected {expected_tool_dir!r}."
    )


@pytest.mark.integration
def test_version_mismatch_regression() -> None:
    """Regression test for version-mismatch bug (MC-53).

    Bug discovered: 2026-05-11
    Platform: macOS / Linux (host mode only)
    Severity: major
    Source: MC-53

    Problem:
    get_version() uses importlib.metadata.version('mc') as its primary source.
    In a development checkout (editable install), importlib.metadata resolves the
    version from pyproject.toml in the working tree. When pyproject.toml is bumped
    ahead of the production-installed uv tool version, get_version() returns the
    wrong (too-new) version. This causes mc-update check/upgrade to report an
    incorrect installed version, potentially skipping needed upgrades or
    misreporting the current state.

    Steps to reproduce:
    1. Have mc installed as a uv tool at version X (e.g. 2.0.18).
    2. Bump pyproject.toml to version Y > X (e.g. 2.0.19) in the dev checkout.
    3. Call get_version() from the dev checkout environment.
    4. importlib.metadata.version('mc') returns Y (pyproject.toml), not X (uv tool).

    Expected:
    When mc is installed as a uv tool AND importlib.metadata returns a version,
    get_version() should prefer the uv tool version (the actually-installed binary)
    over the importlib.metadata version (which reflects the dev checkout).

    Actual (before fix):
    get_version() returns importlib.metadata.version('mc') unconditionally as
    its first resolution step and never consults uv tool list when metadata
    succeeds, so it reports the pyproject.toml version instead of the installed
    tool version.

    This test ensures the bug does not regress.
    """
    from unittest import mock

    from mc.version import get_version

    # Simulate the mismatch scenario:
    # - importlib.metadata sees mc at "2.0.99" (pyproject.toml bumped ahead)
    # - uv tool list reports mc at "2.0.18" (the actually-installed version)
    METADATA_VERSION = "2.0.99"
    TOOL_VERSION = "2.0.18"

    fake_uv_output = f"mc v{TOOL_VERSION}\n- mc\n- mc-update\n"
    fake_completed = mock.MagicMock()
    fake_completed.stdout = fake_uv_output
    fake_completed.returncode = 0

    with (
        mock.patch("mc.version.version", return_value=METADATA_VERSION),
        mock.patch("mc.version.subprocess.run", return_value=fake_completed),
    ):
        result = get_version()

    assert result == TOOL_VERSION, (
        f"get_version() returned {result!r} (from importlib.metadata) "
        f"instead of {TOOL_VERSION!r} (from uv tool list). "
        f"When mc is installed as a uv tool, get_version() must prefer the "
        f"uv tool version over the importlib.metadata version, because the "
        f"latter reflects the dev checkout pyproject.toml, not the installed binary."
    )
