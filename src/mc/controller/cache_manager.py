"""Background cache refresh manager for case metadata.

Manages automatic cache refresh for active cases, reducing Salesforce API
calls while ensuring fresh metadata availability.
"""

import time
import logging
import threading
from typing import Any
from mc.utils.cache import CaseMetadataCache
from mc.integrations.salesforce_api import SalesforceAPIClient
from mc.exceptions import SalesforceAPIError

logger = logging.getLogger(__name__)

# Refresh interval: 4 minutes (before 5-minute TTL expires)
REFRESH_INTERVAL_SECONDS = 240


class CacheManager:
    """Manages case metadata cache with background refresh worker.

    Coordinates automatic cache refresh for tracked case numbers using a
    background worker thread. Handles refresh failures gracefully to prevent
    one case from blocking others.

    Attributes:
        cache: CaseMetadataCache instance
        sf_client: SalesforceAPIClient instance
    """

    def __init__(
        self,
        cache: CaseMetadataCache,
        sf_client: SalesforceAPIClient
    ) -> None:
        """Initialize cache manager.

        Args:
            cache: CaseMetadataCache instance for storage
            sf_client: SalesforceAPIClient instance for API queries
        """
        self.cache = cache
        self.sf_client = sf_client

        # Background worker state
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._case_numbers: list[str] = []
        self._case_numbers_lock = threading.Lock()

    def start_background_refresh(self, case_numbers: list[str]) -> None:
        """Start background refresh worker for tracked cases.

        Args:
            case_numbers: List of case numbers to track for refresh
        """
        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning("Background refresh worker already running")
            return

        # Update tracked case numbers
        with self._case_numbers_lock:
            self._case_numbers = case_numbers.copy()

        # Reset stop event
        self._stop_event.clear()

        # Start worker thread
        self._worker_thread = threading.Thread(
            target=self._refresh_worker,
            daemon=True,
            name="cache-refresh-worker"
        )
        self._worker_thread.start()
        logger.info(
            "Started background refresh worker for %d cases",
            len(case_numbers)
        )

    def stop_background_refresh(self) -> None:
        """Stop background refresh worker gracefully."""
        if not self._worker_thread or not self._worker_thread.is_alive():
            logger.debug("Background refresh worker not running")
            return

        # Signal worker to stop
        self._stop_event.set()

        # Wait for worker to exit (with timeout)
        self._worker_thread.join(timeout=5.0)

        if self._worker_thread.is_alive():
            logger.warning("Background refresh worker did not stop cleanly")
        else:
            logger.info("Background refresh worker stopped")

        self._worker_thread = None

    def _refresh_worker(self) -> None:
        """Background worker thread for cache refresh.

        Runs in a loop, refreshing tracked cases every REFRESH_INTERVAL_SECONDS.
        Handles failures gracefully to prevent one case from blocking others.
        """
        logger.debug("Background refresh worker started")

        while not self._stop_event.is_set():
            # Get snapshot of case numbers (thread-safe)
            with self._case_numbers_lock:
                cases_to_refresh = self._case_numbers.copy()

            # Refresh each case
            for case_number in cases_to_refresh:
                if self._stop_event.is_set():
                    break

                try:
                    self._refresh_case(case_number)
                except Exception as e:
                    # Log error but continue - one failure shouldn't stop all refreshes
                    logger.error(
                        "Failed to refresh cache for case %s: %s",
                        case_number,
                        e
                    )

            # Wait for next refresh interval (or stop signal)
            self._stop_event.wait(timeout=REFRESH_INTERVAL_SECONDS)

        logger.debug("Background refresh worker exiting")

    def _refresh_case(self, case_number: str) -> None:
        """Refresh cache for a single case.

        Fetches fresh metadata from Salesforce API and updates cache.

        Args:
            case_number: Case number to refresh

        Raises:
            SalesforceAPIError: If API query fails
            Exception: For unexpected errors
        """
        try:
            # Query Salesforce for case metadata
            case_data = self.sf_client.query_case(case_number)

            # Extract account data from case response
            # (Salesforce query returns Account.Name in case_data)
            account_data = {
                'name': case_data.get('account_name', '')
            }

            # Update cache
            self.cache.set(case_number, case_data, account_data)

            logger.debug("Refreshed cache for case %s", case_number)

        except SalesforceAPIError as e:
            # API errors are logged but don't stop worker
            logger.error(
                "Salesforce API error refreshing case %s: %s",
                case_number,
                e
            )
            # Re-raise to be caught by worker loop error handler
            raise

        except Exception as e:
            # Unexpected errors logged and re-raised
            logger.error(
                "Unexpected error refreshing case %s: %s",
                case_number,
                e
            )
            raise

    def get_or_fetch(
        self,
        case_number: str
    ) -> tuple[dict[str, Any], dict[str, Any], bool]:
        """Get case metadata from cache or fetch from Salesforce.

        Checks cache first. If cache miss or expired, fetches from API
        and updates cache.

        Args:
            case_number: Case number

        Returns:
            tuple: (case_data, account_data, was_cached)
                - case_data: Case metadata dict
                - account_data: Account metadata dict
                - was_cached: True if data came from cache

        Raises:
            SalesforceAPIError: If API query fails
        """
        # Try cache first
        case_data, account_data, was_cached = self.cache.get(case_number)

        if was_cached:
            logger.debug("Cache hit for case %s", case_number)
            return case_data, account_data, True

        # Cache miss - fetch from API
        logger.debug("Cache miss for case %s, fetching from API", case_number)

        case_data = self.sf_client.query_case(case_number)
        account_data = {
            'name': case_data.get('account_name', '')
        }

        # Update cache
        self.cache.set(case_number, case_data, account_data)

        return case_data, account_data, False
