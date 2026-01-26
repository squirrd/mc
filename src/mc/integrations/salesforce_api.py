"""Salesforce API client for Red Hat Support Case metadata queries."""

import time
import logging
from typing import Any
from simple_salesforce import Salesforce  # type: ignore[attr-defined]
from simple_salesforce.exceptions import SalesforceAuthenticationFailed, SalesforceError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from mc.exceptions import SalesforceAPIError

logger = logging.getLogger(__name__)

# Salesforce token lifetime: 2 hours (7200 seconds)
TOKEN_LIFETIME_SECONDS = 7200

# Proactive refresh threshold: 5 minutes before expiry (300 seconds)
REFRESH_THRESHOLD_SECONDS = 300


class SalesforceAPIClient:
    """Client for Red Hat Salesforce case metadata queries.

    Handles session management, automatic token refresh, and error handling
    for Salesforce API operations. Follows the RedHatAPIClient pattern with
    retry logic and exponential backoff.

    Attributes:
        username: Salesforce username (corporate email)
        password: Salesforce password
        security_token: Salesforce security token
    """

    def __init__(self, username: str, password: str, security_token: str) -> None:
        """Initialize Salesforce API client.

        Args:
            username: Salesforce username (Red Hat corporate email)
            password: Salesforce password
            security_token: Salesforce security token (from email)
        """
        self.username = username
        self.password = password
        self.security_token = security_token
        self._session: Salesforce | None = None
        self._token_expires_at: float = 0.0

    def _create_session(self) -> Salesforce:
        """Create new Salesforce session with OAuth2 authentication.

        Tracks token expiration time for proactive refresh.

        Returns:
            Salesforce: Authenticated Salesforce session

        Raises:
            SalesforceAPIError: If authentication fails
        """
        logger.debug("Creating new Salesforce session for %s", self.username)

        try:
            session = Salesforce(
                username=self.username,
                password=self.password,
                security_token=self.security_token
            )

            # Track token expiration (2 hours from now)
            self._token_expires_at = time.time() + TOKEN_LIFETIME_SECONDS
            logger.debug(
                "Salesforce session created, token expires at %f",
                self._token_expires_at
            )

            return session

        except SalesforceAuthenticationFailed as e:
            raise SalesforceAPIError.from_status_code(
                401,
                f"Authentication failed: {str(e)}"
            )
        except SalesforceError as e:
            raise SalesforceAPIError(f"Failed to create session: {str(e)}")

    def _needs_refresh(self) -> bool:
        """Check if token needs proactive refresh.

        Refreshes when within 5 minutes of expiration to prevent
        mid-operation authentication failures.

        Returns:
            bool: True if token should be refreshed
        """
        if not self._session:
            return True

        time_until_expiry = self._token_expires_at - time.time()
        return time_until_expiry < REFRESH_THRESHOLD_SECONDS

    def _refresh_session(self) -> None:
        """Proactively refresh Salesforce session before token expires.

        Creates new session and updates expiration tracking.
        """
        logger.debug("Refreshing Salesforce session (proactive)")
        self._session = self._create_session()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type(SalesforceAPIError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def query_case(self, case_number: str) -> dict[str, Any]:
        """Query Salesforce for case metadata.

        Fetches case metadata including customer name, cluster ID, summary,
        severity, status, and owner. Automatically refreshes token if needed.

        Args:
            case_number: Salesforce case number (e.g., "12345678")

        Returns:
            dict: Case metadata with keys:
                - case_number: Case number
                - account_name: Customer account name
                - cluster_id: Cluster ID (if present)
                - subject: Case subject/summary
                - severity: Case severity
                - status: Case status
                - owner_name: Case owner name
                - created_date: Case creation date

        Raises:
            SalesforceAPIError: If query fails or case not found
        """
        logger.debug("Querying Salesforce for case %s", case_number)

        # Proactive token refresh
        if self._needs_refresh():
            self._refresh_session()

        # Ensure we have a session
        if not self._session:
            self._session = self._create_session()

        # Build SOQL query for case metadata
        query = (
            f"SELECT CaseNumber, Account.Name, Cluster_ID__c, Subject, "
            f"Severity__c, Status, Owner.Name, CreatedDate "
            f"FROM Case WHERE CaseNumber = '{case_number}'"
        )

        try:
            result = self._session.query(query)

            # Check if case was found
            if not result or not result.get('records'):
                raise SalesforceAPIError.from_status_code(
                    404,
                    f"Case {case_number} not found"
                )

            # Extract first record (CaseNumber is unique)
            record = result['records'][0]

            # Parse response into standardized format
            case_data = {
                'case_number': record.get('CaseNumber', ''),
                'account_name': record.get('Account', {}).get('Name', '') if record.get('Account') else '',
                'cluster_id': record.get('Cluster_ID__c', ''),
                'subject': record.get('Subject', ''),
                'severity': record.get('Severity__c', ''),
                'status': record.get('Status', ''),
                'owner_name': record.get('Owner', {}).get('Name', '') if record.get('Owner') else '',
                'created_date': record.get('CreatedDate', ''),
            }

            logger.debug("Successfully queried case %s", case_number)
            return case_data

        except SalesforceError as e:
            # Parse Salesforce error to get status code
            error_msg = str(e)

            # Check for specific error patterns
            if 'INVALID_SESSION_ID' in error_msg or 'Session expired' in error_msg:
                # Token expired mid-operation - refresh and retry
                logger.warning("Session expired, forcing refresh")
                self._refresh_session()
                raise SalesforceAPIError.from_status_code(401, error_msg)

            elif 'REQUEST_LIMIT_EXCEEDED' in error_msg or '429' in error_msg:
                # Rate limiting
                raise SalesforceAPIError.from_status_code(429, error_msg)

            elif 'INSUFFICIENT_ACCESS' in error_msg:
                # Permission denied
                raise SalesforceAPIError.from_status_code(403, error_msg)

            else:
                # Generic Salesforce error
                raise SalesforceAPIError(f"Query failed: {error_msg}")

    def close(self) -> None:
        """Close Salesforce session and cleanup resources."""
        if self._session:
            # simple-salesforce doesn't have explicit close method
            self._session = None
            logger.debug("Salesforce session closed")

    def __enter__(self) -> 'SalesforceAPIClient':
        """Context manager entry."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any
    ) -> None:
        """Context manager exit."""
        self.close()
