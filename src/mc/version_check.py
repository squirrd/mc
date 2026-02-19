"""Version checking infrastructure for MC CLI."""

import atexit
import logging
import threading
import time
from typing import Optional

from mc.config.manager import ConfigManager

logger = logging.getLogger(__name__)


class VersionChecker:
    """Background version checker with graceful cleanup."""

    THROTTLE_SECONDS = 3600  # 1 hour
    RATE_LIMIT_THROTTLE_SECONDS = 86400  # 24 hours
    GITHUB_OWNER = "dsquire"
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

    def _perform_version_check(self) -> None:
        """Perform version check and update config.

        This method will be fully implemented in Task 2.
        It will fetch latest release from GitHub, compare versions,
        and update config with results.
        """
        pass  # Implementation in Task 2

    def _display_notification(self, current: str, latest: str) -> None:
        """Display update notification to stderr.

        This method will be fully implemented in Task 3.
        It will show a single-line message when updates are available.

        Args:
            current: Current installed version
            latest: Latest available version from GitHub
        """
        pass  # Implementation in Task 3


def check_for_updates() -> None:
    """Convenience function to start background version check.

    Can be called from CLI startup to trigger non-blocking update check.
    """
    checker = VersionChecker()
    checker.start_background_check()
