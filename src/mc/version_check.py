"""Version checking infrastructure for MC CLI."""

import atexit
import logging
import sys
import threading
import time
from typing import Optional

import requests
from packaging.version import Version, InvalidVersion
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

from mc.config.manager import ConfigManager
from mc.version import get_version

logger = logging.getLogger(__name__)


class VersionChecker:
    """Background version checker with graceful cleanup."""

    THROTTLE_SECONDS = 3600  # 1 hour
    RATE_LIMIT_THROTTLE_SECONDS = 86400  # 24 hours
    GITHUB_OWNER = "squirrd"
    GITHUB_REPO = "mc"

    def __init__(self):
        """Initialize version checker."""
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._config_manager = ConfigManager()

    def start_background_check(self) -> None:
        """Launch version check as daemon thread."""
        # Check if already running
        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning("Version check already running")
            return

        # Check throttle before starting
        version_config = self._config_manager.get_version_config()
        last_check = version_config.get('last_check')
        last_status_code = self._config_manager.get('version.last_status_code', None)

        if not self._should_check_now(last_check, last_status_code):
            logger.debug(f"Version check throttled (last check: {last_check})")
            return

        # Create daemon thread
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._check_version_worker,
            daemon=True,
            name="version-check"
        )
        self._worker_thread.start()

        # Register atexit cleanup
        atexit.register(self._cleanup)

        logger.debug("Started background version check")

    def _cleanup(self) -> None:
        """Gracefully stop daemon thread before exit."""
        if not self._worker_thread or not self._worker_thread.is_alive():
            return

        logger.debug("Stopping version check worker")
        self._stop_event.set()

        # Join with 2.0 second timeout
        self._worker_thread.join(timeout=2.0)

        if self._worker_thread.is_alive():
            logger.warning("Version check worker did not stop cleanly")

    def _should_check_now(
        self,
        last_check: Optional[float],
        last_status_code: Optional[int] = None
    ) -> bool:
        """Determine if version check should run.

        Args:
            last_check: Unix timestamp of last check, or None
            last_status_code: HTTP status from last check (extend throttle on 403)

        Returns:
            True if check should run, False if throttled
        """
        if last_check is None:
            return True  # Never checked before

        # Extend throttle to 24 hours on rate limit error
        throttle = (
            self.RATE_LIMIT_THROTTLE_SECONDS
            if last_status_code == 403
            else self.THROTTLE_SECONDS
        )

        elapsed = time.time() - last_check
        return elapsed >= throttle

    def _check_version_worker(self) -> None:
        """Worker thread that performs version check."""
        try:
            # Perform version check (implemented in Task 2)
            self._perform_version_check()
        except Exception as e:
            logger.error(f"Version check failed: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    def _fetch_latest_release(self, etag: Optional[str] = None) -> tuple[Optional[dict], str, int]:
        """Fetch latest release from GitHub with ETag support.

        Args:
            etag: Previous ETag value for conditional request

        Returns:
            Tuple of (release_data, new_etag, status_code)
            - release_data is None if 304 Not Modified
            - new_etag is updated value (or same if 304)
            - status_code for error handling
        """
        url = f'https://api.github.com/repos/{self.GITHUB_OWNER}/{self.GITHUB_REPO}/releases/latest'
        headers = {
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28'
        }

        if etag:
            headers['If-None-Match'] = etag

        response = requests.get(url, headers=headers, timeout=10)

        # Handle 304 Not Modified
        if response.status_code == 304:
            return None, etag, 304

        # Handle 404 — repo has no releases published yet (not a real error)
        if response.status_code == 404:
            return None, '', 404

        # Fail fast on other 4xx errors (don't retry)
        if 400 <= response.status_code < 500:
            response.raise_for_status()

        # 5xx errors will be retried by decorator
        response.raise_for_status()

        new_etag = response.headers.get('ETag', '')
        return response.json(), new_etag, 200

    def _perform_version_check(self) -> None:
        """Perform version check and update config."""
        try:
            # Get current version
            current = get_version()

            # Load version config
            version_config = self._config_manager.get_version_config()
            cached_etag = self._config_manager.get('version.etag', None)
            latest_known = self._config_manager.get('version.latest_known', None)
            latest_known_at = self._config_manager.get('version.latest_known_at', None)

            # Fetch latest release with ETag support
            release_data, new_etag, status_code = self._fetch_latest_release(cached_etag)

            # Load current config for update
            try:
                config = self._config_manager.load()
            except FileNotFoundError:
                from mc.config.models import get_default_config
                config = get_default_config()

            # Ensure [version] section exists
            if 'version' not in config:
                config['version'] = {}

            # Update last_check and last_status_code for all responses
            config['version']['last_check'] = time.time()
            config['version']['last_status_code'] = status_code

            # Handle 404 - no releases published yet
            if status_code == 404:
                logger.debug("No GitHub releases found — version check skipped")
                config['version']['last_check'] = time.time()
                config['version']['last_status_code'] = status_code
                self._config_manager.save_atomic(config)
                return

            # Handle 304 Not Modified - keep cached data, update timestamp only
            if status_code == 304:
                logger.debug("GitHub API returned 304 Not Modified - using cached version data")
                self._config_manager.save_atomic(config)

                # Check if cached version is newer and should display notification
                if latest_known and self._is_newer_version(current, latest_known):
                    self._display_notification(current, latest_known)
                return

            # Handle 200 success - parse release data and update config
            if status_code == 200 and release_data:
                # Extract version from tag_name (e.g., "v2.0.5" -> "2.0.5")
                tag_name = release_data.get('tag_name', '')
                latest_version = tag_name.lstrip('v')

                # Update config with new data
                config['version']['etag'] = new_etag
                config['version']['latest_known'] = latest_version
                config['version']['latest_known_at'] = time.time()

                # Save atomically
                self._config_manager.save_atomic(config)

                logger.debug(f"Version check complete: current={current}, latest={latest_version}")

                # Display notification if newer version available
                if self._is_newer_version(current, latest_version):
                    self._display_notification(current, latest_version)

        except Exception as e:
            logger.error(f"Failed to perform version check: {e}")
            # Silent failure - don't raise exceptions from background thread

    def _is_newer_version(self, current: str, latest: str) -> bool:
        """Check if latest version is newer than current using PEP 440.

        Args:
            current: Current installed version (e.g., "2.0.4")
            latest: Latest available version from GitHub (e.g., "2.0.5")

        Returns:
            True if latest > current, False otherwise
        """
        try:
            return Version(latest) > Version(current)
        except InvalidVersion as e:
            logger.error(f"Invalid version string during comparison: {e}")
            return False

    def _should_display_notification(self, last_notification: Optional[float]) -> bool:
        """Determine if notification should be displayed (once per day max).

        Args:
            last_notification: Unix timestamp of last notification, or None

        Returns:
            True if should display, False if throttled
        """
        if last_notification is None:
            return True  # Never shown before

        elapsed = time.time() - last_notification
        return elapsed >= 86400  # 24 hours = 1 day

    def _display_notification(self, current: str, latest: str) -> None:
        """Display update notification to stderr.

        Format from CONTEXT.md:
        "mc v2.0.6 available. Update: uvx --reinstall mc-cli@latest"

        Args:
            current: Current installed version
            latest: Latest available version from GitHub
        """
        try:
            # Check if should display (once per day)
            last_notification = self._config_manager.get('version.last_notification', None)

            if not self._should_display_notification(last_notification):
                logger.debug(f"Notification throttled (last shown: {last_notification})")
                return

            # Display single-line message to stderr
            message = f"mc v{latest} available. Update: uvx --reinstall mc-cli@latest\n"
            sys.stderr.write(message)
            sys.stderr.flush()

            # Update last_notification timestamp
            try:
                config = self._config_manager.load()
            except FileNotFoundError:
                from mc.config.models import get_default_config
                config = get_default_config()

            # Ensure [version] section exists
            if 'version' not in config:
                config['version'] = {}

            config['version']['last_notification'] = time.time()

            # Save atomically
            self._config_manager.save_atomic(config)

            logger.debug(f"Update notification displayed: v{latest}")

        except Exception as e:
            logger.error(f"Failed to display notification: {e}")
            # Silent failure - don't raise exceptions from background thread


def check_for_updates() -> None:
    """Convenience function to start background version check.

    Can be called from CLI startup to trigger non-blocking update check.
    """
    checker = VersionChecker()
    checker.start_background_check()
