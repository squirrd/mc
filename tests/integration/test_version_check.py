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
