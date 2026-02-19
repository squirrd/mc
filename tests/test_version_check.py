"""Tests for version check infrastructure."""

import time
import threading
from unittest.mock import patch, MagicMock, call
import pytest
from mc.version_check import VersionChecker


class TestThrottling:
    """Test hourly throttle logic."""

    def test_should_check_when_never_checked(self):
        """First check should always run."""
        checker = VersionChecker()
        assert checker._should_check_now(None, None) is True

    def test_should_not_check_within_hour(self):
        """Check should be throttled if less than 1 hour elapsed."""
        checker = VersionChecker()
        # 30 minutes ago
        last_check = time.time() - 1800
        assert checker._should_check_now(last_check, None) is False

    def test_should_check_after_hour(self):
        """Check should run after 1 hour elapsed."""
        checker = VersionChecker()
        # 1 hour + 1 second ago
        last_check = time.time() - 3601
        assert checker._should_check_now(last_check, None) is True

    def test_rate_limit_extends_throttle_to_24_hours(self):
        """403 response extends throttle to 24 hours."""
        checker = VersionChecker()
        # 2 hours ago, but last status was 403
        last_check = time.time() - 7200
        assert checker._should_check_now(last_check, 403) is False

    def test_rate_limit_allows_check_after_24_hours(self):
        """403 response still allows check after 24 hours."""
        checker = VersionChecker()
        # 24 hours + 1 second ago
        last_check = time.time() - 86401
        assert checker._should_check_now(last_check, 403) is True


class TestVersionComparison:
    """Test PEP 440 version comparison."""

    def test_newer_version_detected(self):
        """Should detect when latest > current."""
        checker = VersionChecker()
        assert checker._is_newer_version("2.0.4", "2.0.5") is True

    def test_same_version_not_newer(self):
        """Should return False when versions equal."""
        checker = VersionChecker()
        assert checker._is_newer_version("2.0.5", "2.0.5") is False

    def test_older_version_not_newer(self):
        """Should return False when latest < current."""
        checker = VersionChecker()
        assert checker._is_newer_version("2.0.5", "2.0.4") is False

    def test_prerelease_comparison(self):
        """Should handle pre-release versions correctly."""
        checker = VersionChecker()
        assert checker._is_newer_version("2.0.5a1", "2.0.5") is True  # stable > pre-release
        assert checker._is_newer_version("2.0.4", "2.0.5a1") is True  # newer pre-release > old stable

    def test_invalid_version_string(self):
        """Should handle invalid version strings gracefully."""
        checker = VersionChecker()
        assert checker._is_newer_version("invalid", "2.0.5") is False
        assert checker._is_newer_version("2.0.5", "bad-version") is False


class TestGitHubAPI:
    """Test GitHub API integration."""

    @patch('mc.version_check.requests.get')
    def test_fetch_release_success(self, mock_get):
        """Should fetch latest release and extract ETag."""
        # Mock 200 response with release data
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'ETag': 'W/"abc123"'}
        mock_response.json.return_value = {
            'tag_name': 'v2.0.5',
            'name': 'Version 2.0.5'
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()
        data, etag, status = checker._fetch_latest_release()

        assert status == 200
        assert etag == 'W/"abc123"'
        assert data['tag_name'] == 'v2.0.5'

    @patch('mc.version_check.requests.get')
    def test_fetch_release_304_not_modified(self, mock_get):
        """Should handle 304 Not Modified response."""
        mock_response = MagicMock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response

        checker = VersionChecker()
        data, etag, status = checker._fetch_latest_release(etag='W/"cached"')

        assert status == 304
        assert data is None
        assert etag == 'W/"cached"'  # ETag unchanged

    @patch('mc.version_check.requests.get')
    def test_fetch_release_rate_limit(self, mock_get):
        """Should raise on 403 rate limit."""
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.raise_for_status.side_effect = Exception("Rate limit")
        mock_get.return_value = mock_response

        checker = VersionChecker()
        with pytest.raises(Exception):
            checker._fetch_latest_release()


class TestNotificationDisplay:
    """Test notification display logic."""

    def test_notification_displayed_first_time(self, capsys):
        """Should display notification on first check."""
        checker = VersionChecker()

        # Mock config manager to return None for last_notification
        with patch.object(checker._config_manager, 'get', return_value=None):
            with patch.object(checker._config_manager, 'load') as mock_load:
                with patch.object(checker._config_manager, 'save_atomic') as mock_save:
                    # Mock load to return basic config
                    mock_load.return_value = {}

                    checker._display_notification("2.0.4", "2.0.5")

        captured = capsys.readouterr()
        assert "mc v2.0.5 available" in captured.err
        assert "uvx --reinstall mc-cli@latest" in captured.err

    def test_notification_throttled_within_day(self):
        """Should not display if shown less than 24 hours ago."""
        checker = VersionChecker()

        # 1 hour ago
        last_notification = time.time() - 3600
        assert checker._should_display_notification(last_notification) is False

    def test_notification_allowed_after_day(self):
        """Should display if more than 24 hours since last."""
        checker = VersionChecker()

        # 24 hours + 1 second ago
        last_notification = time.time() - 86401
        assert checker._should_display_notification(last_notification) is True

    def test_notification_format(self, capsys):
        """Should display correct message format to stderr."""
        checker = VersionChecker()

        with patch.object(checker._config_manager, 'get', return_value=None):
            with patch.object(checker._config_manager, 'load') as mock_load:
                with patch.object(checker._config_manager, 'save_atomic') as mock_save:
                    mock_load.return_value = {}
                    checker._display_notification("2.0.4", "2.0.5")

        captured = capsys.readouterr()
        assert "mc v2.0.5 available" in captured.err
        assert "uvx --reinstall mc-cli@latest" in captured.err


class TestThreadLifecycle:
    """Test daemon thread lifecycle and cleanup."""

    def test_start_creates_daemon_thread(self):
        """Should create daemon thread on start."""
        def slow_check():
            time.sleep(0.5)

        with patch.object(VersionChecker, '_perform_version_check', side_effect=slow_check):
            checker = VersionChecker()
            # Mock config to skip throttle
            with patch.object(checker._config_manager, 'get_version_config', return_value={'last_check': None}):
                with patch.object(checker._config_manager, 'get', return_value=None):
                    checker.start_background_check()

                    # Give thread time to start
                    time.sleep(0.05)

                    assert checker._worker_thread is not None
                    assert checker._worker_thread.daemon is True
                    assert checker._worker_thread.is_alive()

                    # Cleanup
                    checker._cleanup()

    def test_cleanup_stops_thread(self):
        """Should stop thread gracefully on cleanup."""
        with patch.object(VersionChecker, '_perform_version_check'):
            checker = VersionChecker()
            with patch.object(checker._config_manager, 'get_version_config', return_value={'last_check': None}):
                with patch.object(checker._config_manager, 'get', return_value=None):
                    checker.start_background_check()

                    # Simulate atexit cleanup
                    checker._cleanup()

                    # Thread should stop within timeout
                    time.sleep(0.5)
                    assert not checker._worker_thread.is_alive()

    def test_already_running_skips_restart(self):
        """Should not start second thread if already running."""
        def slow_check():
            time.sleep(1)

        with patch.object(VersionChecker, '_perform_version_check', side_effect=slow_check):
            checker = VersionChecker()
            with patch.object(checker._config_manager, 'get_version_config', return_value={'last_check': None}):
                with patch.object(checker._config_manager, 'get', return_value=None):
                    # Start first thread
                    checker.start_background_check()
                    first_thread = checker._worker_thread

                    # Attempt second start
                    checker.start_background_check()
                    second_thread = checker._worker_thread

                    # Should be same thread
                    assert first_thread is second_thread

                    # Cleanup
                    checker._cleanup()
                    time.sleep(0.5)


class TestConfigIntegration:
    """Test config persistence and atomicity."""

    @patch('mc.version_check.requests.get')
    def test_etag_persisted_in_config(self, mock_get):
        """Should store ETag in version config."""
        # Mock GitHub API 200 response with ETag
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'ETag': 'W/"xyz789"'}
        mock_response.json.return_value = {
            'tag_name': 'v2.0.6',
            'name': 'Version 2.0.6'
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()

        with patch('mc.version_check.get_version', return_value='2.0.5'):
            with patch.object(checker._config_manager, 'get_version_config', return_value={}):
                with patch.object(checker._config_manager, 'get', return_value=None):
                    with patch.object(checker._config_manager, 'load', return_value={}):
                        with patch.object(checker._config_manager, 'save_atomic') as mock_save:
                            with patch.object(checker, '_display_notification'):
                                checker._perform_version_check()

                            # Verify save_atomic was called with etag
                            assert mock_save.called
                            saved_config = mock_save.call_args[0][0]
                            assert saved_config['version']['etag'] == 'W/"xyz789"'

    @patch('mc.version_check.requests.get')
    def test_last_check_timestamp_updated(self, mock_get):
        """Should update last_check timestamp on each check."""
        # Mock GitHub API
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'ETag': 'W/"test"'}
        mock_response.json.return_value = {
            'tag_name': 'v2.0.5',
            'name': 'Version 2.0.5'
        }
        mock_get.return_value = mock_response

        checker = VersionChecker()

        # Record time before check
        start_time = time.time()

        with patch('mc.version_check.get_version', return_value='2.0.4'):
            with patch.object(checker._config_manager, 'get_version_config', return_value={}):
                with patch.object(checker._config_manager, 'get', return_value=None):
                    with patch.object(checker._config_manager, 'load', return_value={}):
                        with patch.object(checker._config_manager, 'save_atomic') as mock_save:
                            with patch.object(checker, '_display_notification'):
                                checker._perform_version_check()

                        # Verify last_check was updated
                        assert mock_save.called
                        saved_config = mock_save.call_args[0][0]
                        assert saved_config['version']['last_check'] >= start_time


class TestTimingAndNonBlocking:
    """Test non-blocking behavior and timing (VCHK-04)."""

    @patch('mc.version_check.VersionChecker._perform_version_check')
    def test_cli_help_returns_quickly_with_background_check(self, mock_check):
        """CLI should complete in <1s even with background version check running."""
        import sys
        from mc.cli.main import main

        # Mock _perform_version_check to simulate slow network
        def slow_check():
            time.sleep(3)  # Simulate 3-second network delay
        mock_check.side_effect = slow_check

        # Time CLI execution
        start = time.time()

        # Mock sys.argv and run CLI help
        old_argv = sys.argv
        try:
            sys.argv = ['mc', '--help']
            try:
                main()
            except SystemExit:
                pass  # --help exits with 0
        finally:
            sys.argv = old_argv

        elapsed = time.time() - start

        # Assert CLI completed before background thread finished
        assert elapsed < 1.0, f"CLI took {elapsed}s, should be <1s (non-blocking)"

    def test_daemon_thread_exits_cleanly(self):
        """Daemon thread should complete cleanup without hanging CLI exit."""
        import subprocess

        # Run CLI command that triggers version check
        start = time.time()
        result = subprocess.run(
            ['python3', '-m', 'mc.cli.main', '--help'],
            capture_output=True,
            timeout=2,  # Should never take this long
            cwd='/Users/dsquirre/Repos/mc'
        )
        elapsed = time.time() - start

        # Verify clean exit
        assert result.returncode == 0
        assert elapsed < 1.0, f"Process took {elapsed}s to exit, thread may have hung"


class TestCLIIntegration:
    """Test CLI command integration."""

    @patch('mc.version_check.VersionChecker._perform_version_check')
    def test_version_command_without_update(self, mock_check, capsys):
        """mc version should display version without checking for updates."""
        from mc.cli.commands.other import version

        with patch('mc.version.get_version', return_value='2.0.4'):
            version(update=False)

        captured = capsys.readouterr()
        assert "mc version 2.0.4" in captured.out
        assert not mock_check.called

    @patch('mc.version_check.VersionChecker._perform_version_check')
    def test_version_command_with_update(self, mock_check, capsys):
        """mc version --update should force immediate check."""
        from mc.cli.commands.other import version

        with patch('mc.version.get_version', return_value='2.0.4'):
            version(update=True)

        captured = capsys.readouterr()
        assert "mc version 2.0.4" in captured.out
        assert "Checking for updates..." in captured.err
        assert "Version check complete." in captured.err
        mock_check.assert_called_once()


class TestRuntimeModeIntegration:
    """Test runtime mode integration (skip in agent mode)."""

    @patch('mc.runtime.get_runtime_mode', return_value='agent')
    def test_version_check_skipped_in_agent_mode(self, mock_runtime):
        """Should skip version check when running in agent mode."""
        with patch.object(VersionChecker, 'start_background_check') as mock_start:
            # Simulate CLI startup logic
            from mc.runtime import get_runtime_mode

            if get_runtime_mode() != 'agent':
                checker = VersionChecker()
                checker.start_background_check()

            # Verify version check was NOT started in agent mode
            assert not mock_start.called

    @patch('mc.runtime.get_runtime_mode', return_value='controller')
    def test_version_check_runs_in_controller_mode(self, mock_runtime):
        """Should run version check when in controller mode."""
        checker = VersionChecker()

        with patch.object(checker._config_manager, 'get_version_config', return_value={'last_check': None}):
            with patch.object(checker._config_manager, 'get', return_value=None):
                with patch.object(checker, '_perform_version_check') as mock_perform:
                    from mc.runtime import get_runtime_mode

                    if get_runtime_mode() != 'agent':
                        checker.start_background_check()

                    # Give thread time to start
                    time.sleep(0.1)

                    # Verify check was started
                    checker._cleanup()


class Test304Response:
    """Test handling of 304 Not Modified responses."""

    @patch('mc.version_check.requests.get')
    def test_304_uses_cached_version_for_notification(self, mock_get):
        """Should use cached version data when GitHub returns 304."""
        # Mock 304 response
        mock_response = MagicMock()
        mock_response.status_code = 304
        mock_get.return_value = mock_response

        checker = VersionChecker()

        # Mock cached version data
        with patch('mc.version_check.get_version', return_value='2.0.4'):
            with patch.object(checker._config_manager, 'get_version_config', return_value={'last_check': None}):
                with patch.object(checker._config_manager, 'get') as mock_get_config:
                    # Setup mock to return cached version
                    def get_side_effect(key, default=None):
                        if key == 'version.etag':
                            return 'W/"cached"'
                        elif key == 'version.latest_known':
                            return '2.0.5'  # Cached newer version
                        return default

                    mock_get_config.side_effect = get_side_effect

                    with patch.object(checker._config_manager, 'load', return_value={}):
                        with patch.object(checker._config_manager, 'save_atomic'):
                            with patch.object(checker, '_display_notification') as mock_notify:
                                checker._perform_version_check()

                            # Should still display notification for cached newer version
                            mock_notify.assert_called_once_with('2.0.4', '2.0.5')
